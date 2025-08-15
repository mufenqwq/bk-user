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
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from bkuser.apps.data_source.models import DataSource
from bkuser.common.passwd import PasswordRule
from bkuser.plugins.base import get_default_plugin_cfg
from bkuser.plugins.constants import DataSourcePluginEnum
from bkuser.plugins.local.models import LocalDataSourcePluginConfig


class PasswordRuleHandler:
    @staticmethod
    def get_default_password_rule() -> PasswordRule:
        cfg: LocalDataSourcePluginConfig = get_default_plugin_cfg(DataSourcePluginEnum.LOCAL)  # type: ignore
        assert cfg.password_rule is not None
        return cfg.password_rule.to_rule()

    @staticmethod
    def get_data_source_password_rule(data_source: DataSource) -> PasswordRule:
        if not (data_source.is_local and data_source.is_real_type):
            raise ValidationError(_("仅支持本地实名数据源的密码规则获取"))
        plugin_config = data_source.get_plugin_cfg()

        assert isinstance(plugin_config, LocalDataSourcePluginConfig)
        assert plugin_config.password_rule is not None
        if not plugin_config.enable_password:
            raise ValidationError(_("该数据源未启用密码"))

        return plugin_config.password_rule.to_rule()
