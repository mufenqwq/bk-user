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
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone

from bkuser.apps.data_source.constants import DataSourceTypeEnum
from bkuser.apps.data_source.models import DataSource, DataSourceUser, LocalDataSourceIdentityInfo
from bkuser.apps.idp.data_models import gen_data_source_match_rule_of_local
from bkuser.apps.idp.models import Idp
from bkuser.apps.tenant.constants import (
    DEFAULT_TENANT_USER_DISPLAY_NAME_EXPRESSION_CONFIG,
    DEFAULT_TENANT_USER_VALIDITY_PERIOD_CONFIG,
    BuiltInTenantIDEnum,
)
from bkuser.apps.tenant.models import (
    Tenant,
    TenantManager,
    TenantUser,
    TenantUserDisplayNameExpressionConfig,
    TenantUserValidityPeriodConfig,
)
from bkuser.apps.tenant.utils import TenantUserIDGenerator
from bkuser.common.constants import PERMANENT_TIME
from bkuser.common.hashers import make_password
from bkuser.idp_plugins.constants import BuiltinIdpPluginEnum
from bkuser.idp_plugins.local.plugin import LocalIdpPluginConfig
from bkuser.plugins.base import get_default_plugin_cfg
from bkuser.plugins.constants import DataSourcePluginEnum
from bkuser.plugins.local.models import LocalDataSourcePluginConfig


class Command(BaseCommand):
    """
    初始化内置租户
    $ python manage.py init_default_tenant
    """

    @staticmethod
    def _init_tenant_configs(tenant: Tenant):
        """初始化租户配置"""
        # 账户有效期配置
        TenantUserValidityPeriodConfig.objects.get_or_create(
            tenant=tenant,
            defaults=DEFAULT_TENANT_USER_VALIDITY_PERIOD_CONFIG,
        )
        # 用户展示名表达式配置
        TenantUserDisplayNameExpressionConfig.objects.get_or_create(
            tenant=tenant, defaults=DEFAULT_TENANT_USER_DISPLAY_NAME_EXPRESSION_CONFIG
        )

    @staticmethod
    def _init_builtin_data_source(tenant: Tenant):
        """初始化内建管理数据源"""
        data_source, _ = DataSource.objects.get_or_create(
            type=DataSourceTypeEnum.BUILTIN_MANAGEMENT,
            owner_tenant_id=tenant.id,
            defaults={
                "plugin_id": DataSourcePluginEnum.LOCAL,
                "plugin_config": get_default_plugin_cfg(DataSourcePluginEnum.LOCAL),
            },
        )

        return data_source

    @staticmethod
    def _init_admin_user(tenant: Tenant, data_source: DataSource, username: str, password: str) -> TenantUser:
        """初始化管理员用户"""
        data_source_user, _ = DataSourceUser.objects.get_or_create(
            data_source=data_source,
            username=username,
            defaults={
                "code": username,
                "full_name": username,
            },
        )
        LocalDataSourceIdentityInfo.objects.update_or_create(
            user=data_source_user,
            defaults={
                "password": make_password(password),
                "password_updated_at": timezone.now(),
                "password_expired_at": PERMANENT_TIME,
                "data_source": data_source,
                "username": username,
            },
        )
        tenant_user, _ = TenantUser.objects.get_or_create(
            tenant=tenant,
            data_source_user=data_source_user,
            defaults={
                "data_source": data_source,
                "id": TenantUserIDGenerator(tenant.id, data_source).gen(data_source_user),
            },
        )

        return tenant_user

    @staticmethod
    def _init_admin_idp(tenant: Tenant, data_source: DataSource):
        """初始化内置管理员账密登录认证源"""
        Idp.objects.get_or_create(
            name="Administrator",
            plugin_id=BuiltinIdpPluginEnum.LOCAL,
            owner_tenant_id=tenant.id,
            defaults={
                "plugin_config": LocalIdpPluginConfig(data_source_ids=[data_source.id]),
                "data_source_match_rules": [gen_data_source_match_rule_of_local(data_source.id).model_dump()],
                "data_source_id": data_source.id,
            },
        )

    @staticmethod
    def _init_virtual_user(tenant: Tenant, data_source: DataSource, username: str):
        """创建蓝鲸内置虚拟用户"""
        data_source_user, created = DataSourceUser.objects.get_or_create(
            data_source=data_source,
            username=username,
            defaults={
                "full_name": username,
                "code": username,
            },
        )
        if created:
            TenantUser.objects.create(
                id=TenantUserIDGenerator(tenant.id, data_source).gen(data_source_user),
                tenant_id=tenant.id,
                data_source_user=data_source_user,
                data_source=data_source,
            )

    def handle(self, *args, **options):
        # 根据是否开启多租户模式，选择初始化的租户（运营租户或默认租户）
        if settings.ENABLE_MULTI_TENANT_MODE:
            tenant_id = BuiltInTenantIDEnum.SYSTEM
            tenant_name = BuiltInTenantIDEnum.get_choice_label(BuiltInTenantIDEnum.SYSTEM)
        else:
            tenant_id = BuiltInTenantIDEnum.DEFAULT
            tenant_name = BuiltInTenantIDEnum.get_choice_label(BuiltInTenantIDEnum.DEFAULT)

        # 获取管理员账号密码
        admin_username = settings.INITIAL_ADMIN_USERNAME
        admin_password = settings.INITIAL_ADMIN_PASSWORD

        self.stdout.write(
            f"start initialize first tenant[{tenant_id}] & data source with admin user [{admin_username}]..."
        )

        with transaction.atomic():
            # 创建租户
            tenant, _ = Tenant.objects.get_or_create(
                id=tenant_id,
                defaults={
                    "name": tenant_name,
                    "is_default": True,
                },
            )
            # 初始化租户配置
            self._init_tenant_configs(tenant)
            # 初始化内置管理数据源
            data_source = self._init_builtin_data_source(tenant)
            # 初始化管理员成员
            tenant_user = self._init_admin_user(tenant, data_source, admin_username, admin_password)
            # 创建管理成员关联关系
            TenantManager.objects.get_or_create(tenant=tenant, tenant_user=tenant_user)
            # 添加管理员认证源
            self._init_admin_idp(tenant, data_source)
            # 初始化内建虚拟用户
            virtual_data_source, _ = DataSource.objects.get_or_create(
                owner_tenant_id=tenant_id,
                type=DataSourceTypeEnum.VIRTUAL,
                defaults={
                    "plugin_config": LocalDataSourcePluginConfig(enable_password=False),
                    "plugin_id": DataSourcePluginEnum.LOCAL,
                },
            )
            self._init_virtual_user(tenant, virtual_data_source, "bk_admin")

        self.stdout.write(f"Initialized first tenant [{tenant_id}] with admin user [{admin_username}] successfully")
