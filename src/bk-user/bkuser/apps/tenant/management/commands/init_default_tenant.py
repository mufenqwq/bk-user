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

from bkuser.apps.tenant.constants import (
    BuiltInTenantIDEnum,
)
from bkuser.biz.tenant import (
    BuiltinManagementDataSourceConfig,
    BuiltinManagerInfo,
    TenantCreator,
    TenantInfo,
    VirtualUserInfo,
)


class Command(BaseCommand):
    """
    初始化内置租户
    $ python manage.py init_default_tenant
    """

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

        # 创建租户
        TenantCreator.create(
            tenant=TenantInfo(tenant_id=tenant_id, tenant_name=tenant_name, is_default=True),
            builtin_manager=BuiltinManagerInfo(username=admin_username, password=admin_password),
            builtin_ds_config=BuiltinManagementDataSourceConfig(send_password_notification=False),
            virtual_user=VirtualUserInfo(username="bk_admin"),
        )

        self.stdout.write(f"Initialized first tenant [{tenant_id}] with admin user [{admin_username}] successfully")
