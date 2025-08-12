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
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestTenantPasswordRuleRetrieveApi:
    def test_get_tenant_password_rule_success(self, api_client, default_tenant):
        # 调用接口
        url = reverse("tenant.password_rule", kwargs={"id": default_tenant.id})
        response = api_client.get(url)

        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # 验证基本字段
        assert "min_length" in data
        assert "max_length" in data
        assert "contain_lowercase" in data
        assert "contain_uppercase" in data
        assert "contain_digit" in data
        assert "contain_punctuation" in data
        assert "rule_tips" in data
