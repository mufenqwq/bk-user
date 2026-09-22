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
from bkuser.apps.data_source.models import DataSourceDepartment
from bkuser.apps.tenant.models import TenantDepartment, TenantUser
from bkuser.biz.organization import TenantDepartmentHandler, TenantOrgPathHandler

pytestmark = pytest.mark.django_db


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
class TestGetAncestorIdsMap:
    """租户部门祖先 ID 映射测试"""

    def test_empty_input(self, random_tenant):
        assert TenantDepartmentHandler.get_ancestor_ids_map(random_tenant.id, []) == {}

    def test_root_and_nested_departments(self, random_tenant):
        company = TenantDepartment.objects.get(tenant=random_tenant, data_source_department__name="公司")
        dept_a = TenantDepartment.objects.get(tenant=random_tenant, data_source_department__name="部门A")
        center_aa = TenantDepartment.objects.get(tenant=random_tenant, data_source_department__name="中心AA")

        result = TenantDepartmentHandler.get_ancestor_ids_map(
            random_tenant.id,
            [company.data_source_department_id, dept_a.data_source_department_id, center_aa.data_source_department_id],
        )

        assert result[company.id] == []
        assert result[dept_a.id] == [company.id]
        assert result[center_aa.id] == [company.id, dept_a.id]


def _tenant_user(tenant, username: str) -> TenantUser:
    return TenantUser.objects.get(tenant=tenant, data_source_user__username=username)


def _tenant_dept_id(tenant, code: str) -> int:
    return TenantDepartment.objects.get(tenant=tenant, data_source_department__code=code).id


@pytest.mark.usefixtures("_init_tenant_users_depts")
class TestGetUserOrganizationIdsMap:
    """租户用户所属组织 ID 映射测试"""

    def test_empty_input(self):
        assert TenantOrgPathHandler.get_user_organization_ids_map([]) == {}

    def test_user_without_department(self, random_tenant):
        freedom = _tenant_user(random_tenant, "freedom")

        result = TenantOrgPathHandler.get_user_organization_ids_map([freedom])

        assert result[freedom.id] == []

    def test_root_department_user(self, random_tenant):
        """直属根部门时，列表只有根部门自身"""
        zhangsan = _tenant_user(random_tenant, "zhangsan")

        result = TenantOrgPathHandler.get_user_organization_ids_map([zhangsan])

        assert result[zhangsan.id] == [_tenant_dept_id(random_tenant, "company")]

    def test_nested_department_includes_ancestors(self, random_tenant):
        """小组 AAA 上的用户要带上从根到直属部门的整条链"""
        liuqi = _tenant_user(random_tenant, "liuqi")

        result = TenantOrgPathHandler.get_user_organization_ids_map([liuqi])

        assert result[liuqi.id] == [
            _tenant_dept_id(random_tenant, "company"),
            _tenant_dept_id(random_tenant, "dept_a"),
            _tenant_dept_id(random_tenant, "center_aa"),
            _tenant_dept_id(random_tenant, "group_aaa"),
        ]

    def test_multi_org_user_dedup(self, random_tenant):
        """
        王五同时属于部门 A 和部门 B，共享的「公司」只出现一次

        顺序按归属写入顺序：先部门 A 整条链，再补上部门 B
        """
        wangwu = _tenant_user(random_tenant, "wangwu")

        result = TenantOrgPathHandler.get_user_organization_ids_map([wangwu])

        assert result[wangwu.id] == [
            _tenant_dept_id(random_tenant, "company"),
            _tenant_dept_id(random_tenant, "dept_a"),
            _tenant_dept_id(random_tenant, "dept_b"),
        ]
