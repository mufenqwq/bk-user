# -*- coding: utf-8 -*-
# TencentBlueKing is pleased to support the open source community by making
# 蓝鲸智云 - 用户管理 (bk-user) available.
# Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions and
# limitations under the License.
#
# We undertake not to change the open source license (MIT license) applicable
# to the current version of the project delivered to anyone in the future.

import logging
import operator
from functools import reduce
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import BaseModel, Field

from bkuser.apps.data_source.constants import DataSourceTypeEnum
from bkuser.apps.data_source.models import LocalDataSourceIdentityInfo
from bkuser.apps.idp.data_models import gen_data_source_match_rule_of_local
from bkuser.apps.idp.models import Idp
from bkuser.apps.tenant.constants import (
    DEFAULT_TENANT_USER_DISPLAY_NAME_EXPRESSION_CONFIG,
    DEFAULT_TENANT_USER_VALIDITY_PERIOD_CONFIG,
    DISPLAY_NAME_EXPRESSION_FIELD_PATTERN,
    TenantStatus,
)
from bkuser.apps.tenant.display_name_cache import get_display_name_config
from bkuser.apps.tenant.models import (
    DataSource,
    DataSourceUser,
    Tenant,
    TenantManager,
    TenantUser,
    TenantUserCustomField,
    TenantUserDisplayNameExpressionConfig,
    TenantUserValidityPeriodConfig,
    UserBuiltinField,
)
from bkuser.apps.tenant.utils import TenantUserIDGenerator
from bkuser.common.constants import PERMANENT_TIME
from bkuser.common.hashers import make_password
from bkuser.idp_plugins.constants import BuiltinIdpPluginEnum
from bkuser.idp_plugins.local.plugin import LocalIdpPluginConfig
from bkuser.plugins.base import get_default_plugin_cfg
from bkuser.plugins.constants import DataSourcePluginEnum
from bkuser.plugins.local.constants import NEVER_EXPIRE_TIME, NotificationMethod, PasswordGenerateMethod
from bkuser.plugins.local.models import LocalDataSourcePluginConfig
from bkuser.settings import DEFAULT_TENANT_LOGO

logger = logging.getLogger(__name__)


class TenantInfo(BaseModel):
    """租户基础信息配置"""

    tenant_id: str
    tenant_name: str
    logo: str = DEFAULT_TENANT_LOGO
    status: TenantStatus = TenantStatus.ENABLED
    is_default: bool = False


class AdminInfo(BaseModel):
    """内置管理员配置"""

    username: str = "admin"
    password: str = ""
    email: str = ""
    phone: str = ""
    phone_country_code: str = settings.DEFAULT_PHONE_COUNTRY_CODE


class BuiltinDataSourceInitPolicy(BaseModel):
    """内置管理数据源初始化策略（密码与通知）"""

    send_password_notification: bool = True
    fixed_password: str = ""
    notification_methods: List[str] = Field(default_factory=list)


class VirtualUserPolicy(BaseModel):
    """内置虚拟用户策略"""

    create: bool = False
    username: str = "bk_admin"


class TenantCreatePlan(BaseModel):
    """租户创建计划"""

    tenant: TenantInfo
    admin: AdminInfo
    builtin_ds_policy: BuiltinDataSourceInitPolicy
    virtual_user_policy: VirtualUserPolicy


class TenantUserPhoneInfo(BaseModel):
    is_inherited_phone: bool
    custom_phone: Optional[str] = ""
    custom_phone_country_code: Optional[str] = settings.DEFAULT_PHONE_COUNTRY_CODE


class TenantUserEmailInfo(BaseModel):
    is_inherited_email: bool
    custom_email: Optional[str] = ""


class TenantCreate:
    @staticmethod
    def create_tenant_base(info: TenantInfo) -> Tenant:
        """创建租户基础信息"""
        return Tenant.objects.create(
            id=info.tenant_id,
            name=info.tenant_name,
            logo=info.logo,
            status=info.status,
            is_default=info.is_default,
        )

    @staticmethod
    def init_tenant_default_settings(tenant: Tenant) -> None:
        """初始化租户默认配置"""
        # 账号有效期
        TenantUserValidityPeriodConfig.objects.create(tenant=tenant, **DEFAULT_TENANT_USER_VALIDITY_PERIOD_CONFIG)
        # DisplayName 表达式
        TenantUserDisplayNameExpressionConfig.objects.create(
            tenant=tenant, **DEFAULT_TENANT_USER_DISPLAY_NAME_EXPRESSION_CONFIG
        )

    @staticmethod
    def create_builtin_data_source(
        tenant_id: str,
        enable_password: bool = True,
        fixed_password: str = "",
        notification_methods: Optional[List[str]] = None,
    ) -> DataSource:
        """创建内置管理数据源

        :param tenant_id: 租户ID
        :param enable_password: 是否启用密码功能
        :param fixed_password: 固定密码
        :param notification_methods: 通知方式列表
        """
        # 获取本地数据源的默认配置
        plugin_id = DataSourcePluginEnum.LOCAL
        plugin_config = get_default_plugin_cfg(plugin_id)
        assert isinstance(plugin_config, LocalDataSourcePluginConfig)
        assert plugin_config.password_initial is not None
        assert plugin_config.login_limit is not None
        assert plugin_config.password_expire is not None

        # 根据参数配置插件
        if enable_password:
            plugin_config.enable_password = True
            plugin_config.password_expire.valid_time = NEVER_EXPIRE_TIME

            if fixed_password:
                plugin_config.password_initial.generate_method = PasswordGenerateMethod.FIXED
                plugin_config.password_initial.fixed_password = fixed_password

            if notification_methods:
                plugin_config.password_initial.notification.enabled_methods = [
                    NotificationMethod(n) for n in notification_methods
                ]

        return DataSource.objects.create(
            type=DataSourceTypeEnum.BUILTIN_MANAGEMENT,
            owner_tenant_id=tenant_id,
            plugin_id=plugin_id,
            plugin_config=plugin_config,
        )

    @staticmethod
    def create_virtual_data_source(tenant_id: str) -> DataSource:
        """创建虚拟数据源"""
        return DataSource.objects.create(
            owner_tenant_id=tenant_id,
            type=DataSourceTypeEnum.VIRTUAL,
            plugin_config=LocalDataSourcePluginConfig(enable_password=False),
            plugin_id=DataSourcePluginEnum.LOCAL,
        )

    @staticmethod
    def create_builtin_manager(
        tenant: Tenant,
        data_source: DataSource,
        username: str,
        password: str,
        email: str = "",
        phone: str = "",
        phone_country_code: str = "",
    ) -> TenantUser:
        """创建内置管理员"""
        # 创建数据源用户
        data_source_user = DataSourceUser.objects.create(
            data_source=data_source,
            code=username,
            username=username,
            full_name=username,
            email=email,
            phone=phone,
            phone_country_code=phone_country_code,
        )

        # 创建本地身份信息
        if password:
            LocalDataSourceIdentityInfo.objects.create(
                user=data_source_user,
                password=make_password(password),
                password_updated_at=timezone.now(),
                password_expired_at=PERMANENT_TIME,
                data_source=data_source,
                username=username,
            )

        # 创建租户用户
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            data_source_user=data_source_user,
            data_source=data_source,
            id=TenantUserIDGenerator(tenant.id, data_source).gen(data_source_user),
        )

        # 创建管理员关联
        TenantManager.objects.create(tenant=tenant, tenant_user=tenant_user)

        return tenant_user

    @staticmethod
    def create_builtin_virtual_user(tenant: Tenant, data_source: DataSource, username: str) -> TenantUser:
        """创建内置虚拟用户"""
        data_source_user = DataSourceUser.objects.create(
            data_source=data_source,
            username=username,
            full_name=username,
            code=username,
        )

        return TenantUser.objects.create(
            id=TenantUserIDGenerator(tenant.id, data_source).gen(data_source_user),
            tenant_id=tenant.id,
            data_source_user=data_source_user,
            data_source=data_source,
        )

    @staticmethod
    def create_builtin_idp(tenant_id: str, data_source_id: int, name: str = "Administrator") -> Idp:
        """创建内置管理员账密登录认证源"""
        return Idp.objects.create(
            name=name,
            plugin_id=BuiltinIdpPluginEnum.LOCAL,
            owner_tenant_id=tenant_id,
            plugin_config=LocalIdpPluginConfig(data_source_ids=[data_source_id]),
            data_source_match_rules=[gen_data_source_match_rule_of_local(data_source_id).model_dump()],
            data_source_id=data_source_id,
        )

    @classmethod
    def create_tenant(cls, plan: TenantCreatePlan) -> Tenant:
        """创建租户的统一入口方法

        :param plan: 租户创建计划
        :return: 创建的租户对象
        """

        # 注意：校验应由上层完成；此处仅负责创建流程

        with transaction.atomic():
            # 阶段1：创建租户基础信息
            tenant = cls.create_tenant_base(plan.tenant)

            # 阶段2：初始化租户默认配置
            cls.init_tenant_default_settings(tenant)

            # 阶段3：创建内置管理数据源
            data_source = cls.create_builtin_data_source(
                tenant.id,
                enable_password=True,
                fixed_password=plan.builtin_ds_policy.fixed_password,
                notification_methods=plan.builtin_ds_policy.notification_methods
                if plan.builtin_ds_policy.send_password_notification
                else None,
            )

            # 阶段4：创建虚拟数据源
            virtual_data_source = cls.create_virtual_data_source(tenant.id)

            # 阶段5：创建内置管理员
            cls.create_builtin_manager(
                tenant=tenant,
                data_source=data_source,
                username=plan.admin.username,
                password=plan.admin.password,
                email=plan.admin.email,
                phone=plan.admin.phone,
                phone_country_code=plan.admin.phone_country_code,
            )

            # 阶段6：创建内置虚拟用户
            if plan.virtual_user_policy.create:
                cls.create_builtin_virtual_user(tenant, virtual_data_source, plan.virtual_user_policy.username)

            # 阶段7：创建内置认证源
            cls.create_builtin_idp(tenant.id, data_source.id)

        return tenant


class TenantUserHandler:
    @staticmethod
    def update_tenant_user_phone(tenant_user: TenantUser, phone_info: TenantUserPhoneInfo):
        tenant_user.is_inherited_phone = phone_info.is_inherited_phone
        if not phone_info.is_inherited_phone:
            tenant_user.custom_phone = phone_info.custom_phone
            tenant_user.custom_phone_country_code = phone_info.custom_phone_country_code
        tenant_user.save()

    @staticmethod
    def update_tenant_user_email(tenant_user: TenantUser, email_info: TenantUserEmailInfo):
        tenant_user.is_inherited_email = email_info.is_inherited_email
        if not email_info.is_inherited_email:
            tenant_user.custom_email = email_info.custom_email
        tenant_user.save()


class TenantUserDisplayNameHandler:
    @staticmethod
    def generate_tenant_user_display_name(user: TenantUser) -> str:
        """生成租户用户展示名"""
        config = get_display_name_config(user.tenant_id, user.data_source_id)
        return TenantUserDisplayNameHandler.render_display_name(user, config)

    @staticmethod
    def batch_generate_tenant_user_display_name(users: List[TenantUser]) -> Dict[str, str]:
        """
        批量生成租户用户展示名

        注意：调用时需要提前连表查询 `data_source_user`，否则会导致 N+1 问题
        """

        if not users:
            return {}

        # TODO：后续加入缓存逻辑
        # 1. 先获取 display_name 缓存
        # 2. 对于缓存不存在的用户，则执行 batch_render_display_name 方法进行渲染
        # 3. 将渲染后的结果保存到缓存中

        return TenantUserDisplayNameHandler.batch_render_display_name(users)

    @staticmethod
    def get_tenant_user_display_name_map_by_ids(tenant_user_ids: List[str]) -> Dict[str, str]:
        """
        根据指定的租户用户 ID 列表，获取对应的展示用名称列表

        :return: {user_id: user_display_name}
        """
        # 1. 尝试从 TenantUser 表根据表达式渲染出展示用名称（使用批量处理）
        users = TenantUser.objects.select_related("data_source_user").filter(id__in=tenant_user_ids)
        display_name_map = TenantUserDisplayNameHandler.batch_generate_tenant_user_display_name(users)

        # 2. 针对可能出现的 TenantUser 中被删除的 user_id，尝试从 User 表获取展示用名称（登录过就有记录）
        if not_exists_user_ids := set(tenant_user_ids) - set(display_name_map.keys()):
            logger.warning(
                "tenant user ids: %s not exists in TenantUser model, try find display name in User Model",
                not_exists_user_ids,
            )
            UserModel = get_user_model()  # noqa: N806
            for user in UserModel.objects.filter(username__in=not_exists_user_ids):
                # FIXME (nan) get_property 有 N+1 的风险，需要处理
                display_name_map[user.username] = user.get_property("display_name") or user.username

        # 3. 前两种方式都失效，那就给啥 user_id 就返回啥，避免调用的地方还需要处理
        if not_exists_user_ids := set(tenant_user_ids) - set(display_name_map.keys()):
            display_name_map.update({user_id: user_id for user_id in not_exists_user_ids})

        return display_name_map

    @staticmethod
    def parse_display_name_expression(tenant_id: str, expression: str) -> Dict[str, List[str]]:
        """解析展示名表达式，返回格式为 {builtin: [内置字段列表], custom: [自定义字段列表], extra: [额外字段列表]}"""
        fields = DISPLAY_NAME_EXPRESSION_FIELD_PATTERN.findall(expression)

        # TODO: 后续需要过滤敏感字段，敏感字段不支持展示
        builtin_field_names = {field.name for field in UserBuiltinField.objects.all()}

        custom_field_names = {field.name for field in TenantUserCustomField.objects.filter(tenant_id=tenant_id)}

        # TODO: 后续支持 extra 字段
        # 集合运算 & 求交集，比遍历判断更高效
        return {
            "builtin": list(set(fields) & builtin_field_names),
            "custom": list(set(fields) & custom_field_names),
            "extra": [],
        }

    @staticmethod
    def render_display_name(user: TenantUser, config: TenantUserDisplayNameExpressionConfig) -> str:
        """渲染用户展示名"""

        # 获取各类字段值
        builtin_values = TenantUserDisplayNameHandler._get_builtin_field_values(user, config.builtin_fields)
        custom_values = TenantUserDisplayNameHandler._get_custom_field_values(user, config.custom_fields)

        field_value_map = {}
        field_value_map.update(builtin_values)
        field_value_map.update(custom_values)

        # 使用正则表达式替换表达式中的字段为对应值
        # match 是正则表达式从表达式（expression）中匹配到的对象，group(1) 是匹配到的第一个分组，即字段名
        # 如果字段名在 field_value_map 中存在，则使用 field_value_map 中的值替换，否则使用 "-"
        return DISPLAY_NAME_EXPRESSION_FIELD_PATTERN.sub(
            lambda match: field_value_map.get(match.group(1), "-"), config.expression
        )

    @staticmethod
    def batch_render_display_name(
        users: List[TenantUser],
    ) -> Dict[str, str]:
        """批量渲染用户展示用名称"""
        if not users:
            return {}

        user_display_name_map: Dict[str, str] = {}

        # 遍历所有用户，渲染 display_name
        for user in users:
            field_value_map = {}
            config = get_display_name_config(user.tenant_id, user.data_source_id)

            builtin_values = TenantUserDisplayNameHandler._get_builtin_field_values(user, config.builtin_fields)
            custom_values = TenantUserDisplayNameHandler._get_custom_field_values(user, config.custom_fields)

            field_value_map.update(builtin_values)
            field_value_map.update(custom_values)

            # 使用表达式模板渲染展示名
            user_display_name_map[user.id] = DISPLAY_NAME_EXPRESSION_FIELD_PATTERN.sub(
                lambda match, field_value_map=field_value_map: field_value_map.get(match.group(1), "-"),  # type: ignore
                config.expression,
            )

        return user_display_name_map

    @staticmethod
    def _get_builtin_field_values(user: TenantUser, builtin_fields: List[str]) -> Dict[str, str]:
        """处理内置字段"""
        # TODO: 内建字段后续可能也存在协同字段映射的情况，需要处理
        # 联系方式字段映射
        field_value_map = {}

        # 联系信息字段映射
        contact_info = {
            "email": user.email,
            "phone": user.phone_info[0],
            "phone_country_code": user.phone_info[1],
        }

        for field in builtin_fields:
            if field in contact_info:
                field_value_map[field] = contact_info[field] or "-"
            else:
                field_value_map[field] = getattr(user.data_source_user, field)
        return field_value_map

    @staticmethod
    def _get_custom_field_values(user: TenantUser, custom_fields: List[str]) -> Dict[str, str]:
        """处理自定义字段"""
        return {field: str(user.data_source_user.extras.get(field, "-")) for field in custom_fields}

    @staticmethod
    def build_display_name_search_queries(tenant_id: str, keyword: str) -> Q:
        """根据不同字段类型构建展示名搜索查询条件"""
        config = get_display_name_config(tenant_id)

        # 构建内置字段查询条件
        builtin_queries = TenantUserDisplayNameHandler._build_builtin_field_queries(config.builtin_fields, keyword)
        # 为什么不构建自定义字段查询条件？
        # 因为自定义字段存储在 extra 字段（JsonField）中，进行模糊搜索非常消耗资源，JSON 数据需要解析与字符串匹配

        if not builtin_queries:
            return Q()

        field_queries = reduce(operator.or_, builtin_queries)
        return field_queries & Q(data_source__owner_tenant_id=tenant_id)

    @staticmethod
    def _build_builtin_field_queries(builtin_fields: List[str], keyword: str) -> List[Q]:
        """构建内置字段查询条件"""
        inherit_flag_mapping = {"phone_country_code": "phone", "phone": "phone", "email": "email"}
        queries = []

        for field in builtin_fields:
            if field in inherit_flag_mapping:
                inherit_flag = f"is_inherited_{inherit_flag_mapping[field]}"
                queries.append(
                    Q(**{inherit_flag: False, f"custom_{field}__icontains": keyword})
                    | Q(**{inherit_flag: True, f"data_source_user__{field}__icontains": keyword})
                )
            else:
                queries.append(Q(**{f"data_source_user__{field}__icontains": keyword}))

        return queries

    @staticmethod
    def build_default_preview_tenant_user(tenant_id: str) -> TenantUser:
        return TenantUser(
            id="517hMkqnSBqF9Mv9",
            data_source=DataSource(owner_tenant_id=tenant_id),
            tenant_id=tenant_id,
            data_source_user=DataSourceUser(
                username="zhangsan",
                full_name="张三",
                phone="13512345671",
                phone_country_code="86",
                email="zhangsan@m.com",
            ),
        )
