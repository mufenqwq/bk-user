# -*- coding: utf-8 -*-
# TencentBlueKing is pleased to support the open source community by making
# 蓝鲸智云 - 用户管理 (bk-user) available.
# Copyright (C) 2017 Tencent. All rights reserved.
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

from typing import List

import pytest
from bkuser.apps.data_source.models import DataSourceDepartment, DataSourceUser
from bkuser.apps.tenant.models import TenantDepartment
from bkuser.biz.organization import TenantOrgPathHandler

pytestmark = pytest.mark.django_db


def _tenant_dept_id(tenant, code: str) -> int:
    return TenantDepartment.objects.get(tenant=tenant, data_source_department__code=code).id


@pytest.mark.usefixtures("_init_tenant_users_depts")
class TestQueryOrganizationPath:
    """组织路径查询测试"""

    def test_query_org_path_include_self(self):
        """测试包含自身的组织路径"""
        group_aaa = DataSourceDepartment.objects.get(code="group_aaa")
        group_aba = DataSourceDepartment.objects.get(code="group_aba")

        data_source_department_ids = [group_aaa.id, group_aba.id]

        result = TenantOrgPathHandler._query_org_path(data_source_department_ids, include_self=True)

        assert result[group_aaa.id] == "公司/部门A/中心AA/小组AAA"
        assert result[group_aba.id] == "公司/部门A/中心AB/小组ABA"

    def test_query_org_path_exclude_self(self):
        """测试不包含自身的组织路径"""
        group_aaa = DataSourceDepartment.objects.get(code="group_aaa")
        center_ab = DataSourceDepartment.objects.get(code="center_ab")

        data_source_department_ids = [group_aaa.id, center_ab.id]

        result = TenantOrgPathHandler._query_org_path(data_source_department_ids, include_self=False)

        assert result[group_aaa.id] == "公司/部门A/中心AA"
        assert result[center_ab.id] == "公司/部门A"

    def test_query_org_path_root_department(self):
        """测试根部门的组织路径"""
        company = DataSourceDepartment.objects.get(code="company")

        data_source_department_ids = [company.id]

        result = TenantOrgPathHandler._query_org_path(data_source_department_ids, include_self=True)

        assert result[company.id] == "公司"

    def test_query_org_path_with_empty_input(self):
        """测试空输入"""
        data_source_department_ids: List[int] = []
        result = TenantOrgPathHandler._query_org_path(data_source_department_ids, include_self=True)
        assert result == {}


@pytest.mark.usefixtures("_init_tenant_users_depts")
class TestGetUserOrganizationIdPathsMap:
    """用户组织 ID 路径查询测试"""

    def test_single_root_department(self, random_tenant):
        """直属根部门时，路径只包含根部门自身"""
        zhangsan = DataSourceUser.objects.get(username="zhangsan")

        result = TenantOrgPathHandler.get_user_organization_id_paths_map(random_tenant.id, [zhangsan.id])

        assert result[zhangsan.id] == [[_tenant_dept_id(random_tenant, "company")]]

    def test_deep_department_path(self, random_tenant):
        """路径从根组织到直属部门，包含直属部门"""
        liuqi = DataSourceUser.objects.get(username="liuqi")

        result = TenantOrgPathHandler.get_user_organization_id_paths_map(random_tenant.id, [liuqi.id])

        assert result[liuqi.id] == [
            [
                _tenant_dept_id(random_tenant, "company"),
                _tenant_dept_id(random_tenant, "dept_a"),
                _tenant_dept_id(random_tenant, "center_aa"),
                _tenant_dept_id(random_tenant, "group_aaa"),
            ]
        ]

    def test_multi_departments(self, random_tenant):
        """多组织人员返回全部组织路径"""
        lisi = DataSourceUser.objects.get(username="lisi")

        result = TenantOrgPathHandler.get_user_organization_id_paths_map(random_tenant.id, [lisi.id])

        assert set(map(tuple, result[lisi.id])) == {
            (_tenant_dept_id(random_tenant, "company"), _tenant_dept_id(random_tenant, "dept_a")),
            (
                _tenant_dept_id(random_tenant, "company"),
                _tenant_dept_id(random_tenant, "dept_a"),
                _tenant_dept_id(random_tenant, "center_aa"),
            ),
        }

    def test_user_without_department(self, random_tenant):
        """无组织人员返回空数组"""
        freedom = DataSourceUser.objects.get(username="freedom")

        result = TenantOrgPathHandler.get_user_organization_id_paths_map(random_tenant.id, [freedom.id])

        assert result[freedom.id] == []

    def test_empty_input(self, random_tenant):
        assert TenantOrgPathHandler.get_user_organization_id_paths_map(random_tenant.id, []) == {}
