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
from django.core.management.base import BaseCommand

from bkuser.apps.data_source.constants import DataSourceTypeEnum
from bkuser.apps.data_source.models import DataSource
from bkuser.apps.idp.models import Idp
from bkuser.apps.tenant.constants import BuiltInTenantIDEnum
from bkuser.apps.tenant.models import Tenant
from bkuser.idp_plugins.constants import BuiltinIdpPluginEnum


class Command(BaseCommand):
    """获取内置管理员登录地址"""

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=str, help="Tenant ID")

    @staticmethod
    def _check_tenant(tenant_id: str):
        if not Tenant.objects.filter(id=tenant_id).exists():
            raise ValueError(f"tenant {tenant_id} is not existed")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant-id")

        # 兼容非多租户版本
        if not tenant_id:
            tenant_id = (
                BuiltInTenantIDEnum.SYSTEM if settings.ENABLE_MULTI_TENANT_MODE else BuiltInTenantIDEnum.DEFAULT
            )

        self._check_tenant(tenant_id)

        builtin_management_ds = DataSource.objects.get(
            owner_tenant_id=tenant_id,
            type=DataSourceTypeEnum.BUILTIN_MANAGEMENT,
        )

        local_idp = Idp.objects.get(
            owner_tenant_id=tenant_id,
            plugin_id=BuiltinIdpPluginEnum.LOCAL,
            data_source_id=builtin_management_ds.id,
        )

        base_login_url = settings.BK_LOGIN_URL.rstrip("/")
        login_url = f"{base_login_url}/builtin-management-auth/idps/{local_idp.id}/"

        self.stdout.write(login_url)
