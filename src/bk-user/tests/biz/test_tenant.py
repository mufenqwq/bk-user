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

import pytest
from bkuser.apps.data_source.constants import DataSourceTypeEnum
from bkuser.apps.data_source.models import DataSource, LocalDataSourceIdentityInfo
from bkuser.apps.idp.models import Idp
from bkuser.apps.tenant.constants import BuiltInTenantIDEnum, TenantStatus
from bkuser.apps.tenant.models import (
    Tenant,
    TenantManager,
    TenantUser,
    TenantUserDisplayNameExpressionConfig,
    TenantUserValidityPeriodConfig,
)
from bkuser.biz.tenant import TenantCreateConfig, TenantCreateHandler
from bkuser.plugins.constants import DataSourcePluginEnum

pytestmark = pytest.mark.django_db


class TestTenantCreateHandler:
    def test_validate_tenant_id_already_exists(self):
        """测试租户ID已存在"""
        # 创建测试租户
        Tenant.objects.create(id="existing-tenant", name="Existing Tenant")

        with pytest.raises(ValueError, match="already exists"):
            TenantCreateHandler.validate_tenant_id("existing-tenant")

    def test_validate_tenant_id_reserved(self):
        """测试租户ID是保留字"""
        with pytest.raises(ValueError, match="is reserved"):
            TenantCreateHandler.validate_tenant_id(BuiltInTenantIDEnum.SYSTEM)

    def test_validate_password_success(self):
        """测试密码验证成功"""
        # 使用一个符合规则的密码
        TenantCreateHandler.validate_password("Passwd-123456!")

    def test_validate_password_invalid(self):
        """测试密码验证失败"""
        with pytest.raises(ValueError, match="does not meet the password rules"):
            TenantCreateHandler.validate_password("123")

    def test_create_tenant_base(self):
        """测试创建租户基础信息"""
        config = TenantCreateConfig(
            tenant_id="test-tenant",
            tenant_name="Test Tenant",
            logo="test-logo",
            status=TenantStatus.ENABLED,
            is_default=False,
        )

        tenant = TenantCreateHandler.create_tenant_base(config)

        assert tenant.id == "test-tenant"
        assert tenant.name == "Test Tenant"
        assert tenant.logo == "test-logo"
        assert tenant.status == TenantStatus.ENABLED
        assert not tenant.is_default

    def test_init_tenant_default_settings(self):
        """测试初始化租户默认配置"""
        tenant = Tenant.objects.create(id="test-tenant", name="Test Tenant")

        TenantCreateHandler.init_tenant_default_settings(tenant)

        # 验证配置已创建
        assert TenantUserValidityPeriodConfig.objects.filter(tenant=tenant).exists()
        assert TenantUserDisplayNameExpressionConfig.objects.filter(tenant=tenant).exists()

    def test_create_simple_builtin_data_source(self):
        """测试创建简单的内建管理数据源"""
        data_source = TenantCreateHandler.create_simple_builtin_data_source("test-tenant")

        assert data_source.type == DataSourceTypeEnum.BUILTIN_MANAGEMENT
        assert data_source.owner_tenant_id == "test-tenant"

    def test_create_builtin_management_data_source(self):
        """测试创建复杂的内建管理数据源"""
        data_source = TenantCreateHandler.create_complex_builtin_data_source(
            "test-tenant", "Passwd-123456!", ["email"]
        )

        assert data_source.type == DataSourceTypeEnum.BUILTIN_MANAGEMENT
        assert data_source.owner_tenant_id == "test-tenant"

    def test_create_virtual_data_source(self):
        """测试创建虚拟数据源"""
        data_source = TenantCreateHandler.create_virtual_data_source("test-tenant")

        assert data_source.type == DataSourceTypeEnum.VIRTUAL
        assert data_source.owner_tenant_id == "test-tenant"

    def test_create_builtin_manager(self):
        """测试创建内置管理员"""
        tenant = Tenant.objects.create(id="test-tenant", name="Test Tenant")
        # 使用 TenantCreateHandler 的方法来创建数据源，确保配置正确
        data_source = TenantCreateHandler.create_simple_builtin_data_source(tenant.id)

        tenant_user = TenantCreateHandler.create_builtin_manager(
            tenant=tenant,
            data_source=data_source,
            username="admin",
            password="Passwd-123456!",
            email="admin@test.com",
            phone="13800138000",
            phone_country_code="86",
        )

        assert tenant_user.tenant == tenant
        assert tenant_user.data_source == data_source

        # 验证数据源用户
        data_source_user = tenant_user.data_source_user
        assert data_source_user.username == "admin"
        assert data_source_user.email == "admin@test.com"
        assert data_source_user.phone == "13800138000"
        assert data_source_user.phone_country_code == "86"

        # 验证本地身份信息
        identity_info = LocalDataSourceIdentityInfo.objects.get(user=data_source_user)
        assert identity_info.data_source == data_source
        assert identity_info.username == "admin"

        # 验证管理员关联
        assert TenantManager.objects.filter(tenant=tenant, tenant_user=tenant_user).exists()

    def test_create_builtin_virtual_user(self):
        """测试创建内置虚拟用户"""
        tenant = Tenant.objects.create(id="test-tenant", name="Test Tenant")
        data_source = DataSource.objects.create(
            type=DataSourceTypeEnum.VIRTUAL,
            owner_tenant_id=tenant.id,
            plugin_id=DataSourcePluginEnum.LOCAL,
        )

        tenant_user = TenantCreateHandler.create_builtin_virtual_user(
            tenant=tenant, data_source=data_source, username="bk_admin"
        )

        assert tenant_user.tenant == tenant
        assert tenant_user.data_source == data_source

        # 验证数据源用户
        data_source_user = tenant_user.data_source_user
        assert data_source_user.username == "bk_admin"
        assert data_source_user.full_name == "bk_admin"

    def test_create_builtin_idp(self):
        """测试创建内置认证源"""
        # 使用 TenantCreateHandler 的方法来创建数据源，确保配置正确
        data_source = TenantCreateHandler.create_simple_builtin_data_source("test-tenant")

        idp = TenantCreateHandler.create_builtin_idp("test-tenant", data_source.id)

        assert idp.owner_tenant_id == "test-tenant"
        assert idp.data_source_id == data_source.id
        assert idp.name == "Administrator"

    def test_create_tenant_via_command(self):
        """测试通过命令行创建租户"""
        tenant = TenantCreateHandler.create_tenant_via_command("test-tenant", "Passwd-123456!")

        assert tenant.id == "test-tenant"
        assert tenant.name == "test-tenant"

        # 验证数据源
        builtin_data_source = DataSource.objects.get(
            owner_tenant_id=tenant.id, type=DataSourceTypeEnum.BUILTIN_MANAGEMENT
        )
        DataSource.objects.get(owner_tenant_id=tenant.id, type=DataSourceTypeEnum.VIRTUAL)

        # 验证管理员用户
        admin_user = TenantUser.objects.get(tenant=tenant, data_source=builtin_data_source)
        assert admin_user.data_source_user.username == "admin"

        # 验证认证源
        idp = Idp.objects.get(owner_tenant_id=tenant.id)
        assert idp.name == "Administrator"

    def test_init_default_tenant(self):
        """测试初始化默认租户"""
        tenant = TenantCreateHandler.init_default_tenant("test-system", "Test System", "admin", "Passwd-123456!")

        assert tenant.id == "test-system"
        assert tenant.name == "Test System"
        assert tenant.is_default

        # 验证数据源
        builtin_data_source = DataSource.objects.get(
            owner_tenant_id=tenant.id, type=DataSourceTypeEnum.BUILTIN_MANAGEMENT
        )
        virtual_data_source = DataSource.objects.get(owner_tenant_id=tenant.id, type=DataSourceTypeEnum.VIRTUAL)

        # 验证管理员用户
        admin_user = TenantUser.objects.get(tenant=tenant, data_source=builtin_data_source)
        assert admin_user.data_source_user.username == "admin"

        # 验证虚拟用户（只有默认租户才有）
        virtual_user = TenantUser.objects.get(tenant=tenant, data_source=virtual_data_source)
        assert virtual_user.data_source_user.username == "bk_admin"

        # 验证认证源
        idp = Idp.objects.get(owner_tenant_id=tenant.id)
        assert idp.name == "Administrator"

    def test_create_tenant_via_web_api(self):
        """测试通过Web API创建租户"""
        tenant = TenantCreateHandler.create_tenant_via_web_api(
            tenant_id="test-web-tenant",
            tenant_name="Test Web Tenant",
            logo="web-logo",
            status=TenantStatus.ENABLED,
            fixed_password="Passwd-123456!",
            notification_methods=["email"],
            email="admin@test.com",
            phone="13800138000",
            phone_country_code="86",
        )

        assert tenant.id == "test-web-tenant"
        assert tenant.name == "Test Web Tenant"
        assert tenant.logo == "web-logo"
        assert tenant.status == TenantStatus.ENABLED

        # 验证数据源
        builtin_data_source = DataSource.objects.get(
            owner_tenant_id=tenant.id, type=DataSourceTypeEnum.BUILTIN_MANAGEMENT
        )
        virtual_data_source = DataSource.objects.get(owner_tenant_id=tenant.id, type=DataSourceTypeEnum.VIRTUAL)

        # 验证管理员用户
        admin_user = TenantUser.objects.get(tenant=tenant, data_source=builtin_data_source)
        assert admin_user.data_source_user.username == "admin"
        assert admin_user.data_source_user.email == "admin@test.com"
        assert admin_user.data_source_user.phone == "13800138000"
        assert admin_user.data_source_user.phone_country_code == "86"

        # 验证没有虚拟用户
        assert not TenantUser.objects.filter(tenant=tenant, data_source=virtual_data_source).exists()

        # 验证认证源
        idp = Idp.objects.get(owner_tenant_id=tenant.id)
        assert idp.name == "Administrator"
