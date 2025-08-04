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
import os

from django.db import migrations

logger = logging.getLogger(__name__)


def forwards_func(apps, schema_editor):
    """初始化本地数据源插件"""
    if os.getenv("SKIP_INIT_DEFAULT_TENANT", "false").lower() == "true":
        logger.info("skip initialize first tenant & data source")
        return


class Migration(migrations.Migration):
    dependencies = [
        ("tenant", "0002_init_builtin_user_fields"),
        ("data_source", "0002_init_builtin_data_source_plugin"),
        ("idp", "0002_init_builtin_idp_plugin"),
    ]

    operations = [migrations.RunPython(forwards_func)]
