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

from django.core.management.base import BaseCommand

from bkuser.biz.tenant import TenantCreateHandler


class Command(BaseCommand):
    """
    创建租户
    $ python manage.py create_tenant
    """

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", type=str, help="Tenant ID", required=True)
        parser.add_argument("--password", type=str, help="Built-In Manager - admin password", required=True)

    def handle(self, *args, **kwargs):
        tenant_id = kwargs["tenant_id"]
        password = kwargs["password"]

        tenant = TenantCreateHandler.create_tenant_via_command(tenant_id, password)

        # 创建租户成功提示
        self.stdout.write(
            f"create tenant [{tenant.id}] successfully, "
            "you can use admin/password to login and manage tenant organization data"
        )
