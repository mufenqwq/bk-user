# -*- coding: utf-8 -*-
# TencentBlueKing is pleased to support the open source community by making
# 蓝鲸智云 - 用户管理 (bk-user) available.
# Copyright (C) 2017 Tencent. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions and
# limitations under the License.
#
# We undertake not to change the open source license (MIT license) applicable
# to the current version of the project delivered to anyone in the future.

from collections import defaultdict

from django.db import migrations, models

MAX_NAME_LENGTH = 64
TYPE_DEFAULT_NAME = {
    "builtin_management": "内置管理数据源",
    "virtual": "虚拟用户数据源",
}


def _generate_unique_name(base: str, used_names: set[str]) -> str:
    """生成不超过字段长度的租户内唯一名称"""
    base = (base or "数据源")[:MAX_NAME_LENGTH]
    candidate = base
    index = 2
    while candidate.casefold() in used_names:
        suffix = f" {index}"
        candidate = f"{base[: MAX_NAME_LENGTH - len(suffix)]}{suffix}"
        index += 1
    return candidate


def forwards_func(apps, schema_editor):
    """为已有数据源按租户回填唯一名称"""
    DataSource = apps.get_model("data_source", "DataSource")
    data_sources_by_tenant = defaultdict(list)
    for data_source in DataSource.objects.select_related("plugin").order_by("id"):
        data_sources_by_tenant[data_source.owner_tenant_id].append(data_source)

    for data_sources in data_sources_by_tenant.values():
        used_names: set[str] = set()
        for data_source in data_sources:
            base_name = TYPE_DEFAULT_NAME.get(data_source.type) or data_source.plugin.name
            data_source.name = _generate_unique_name(base_name, used_names)
            used_names.add(data_source.name.casefold())
            data_source.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("data_source", "0003_datasource_multi_source_support")]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="name",
            field=models.CharField(default="", max_length=MAX_NAME_LENGTH, verbose_name="数据源名称"),
            preserve_default=False,
        ),
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="datasource",
            unique_together={("name", "owner_tenant_id")},
        ),
    ]
