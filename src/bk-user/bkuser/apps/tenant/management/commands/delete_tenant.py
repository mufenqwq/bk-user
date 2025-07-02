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

from django.db import transaction
from django.db.models import Q

from bkuser.apps.data_source.models import (
    DataSource,
    DataSourceDepartment,
    DataSourceDepartmentRelation,
    DataSourceDepartmentUserRelation,
    DataSourceSensitiveInfo,
    DataSourceUser,
    DataSourceUserLeaderRelation,
    DepartmentRelationMPTTTree,
)
from bkuser.apps.idp.models import Idp, IdpSensitiveInfo
from bkuser.apps.tenant.models import (
    CollaborationStrategy,
    Tenant,
    TenantCommonVariable,
    TenantDepartment,
    TenantDepartmentIDRecord,
    TenantManager,
    TenantUser,
    TenantUserCustomField,
    TenantUserDisplayNameExpressionConfig,
    TenantUserIDGenerateConfig,
    TenantUserIDRecord,
    TenantUserValidityPeriodConfig,
    VirtualUserAppRelation,
    VirtualUserOwnerRelation,
)


def delete_tenant_and_related_data(tenant_id: str):
    with transaction.atomic():
        tenant_user_ids = list(TenantUser.objects.filter(tenant_id=tenant_id).values_list("id", flat=True))
        VirtualUserAppRelation.objects.filter(tenant_user_id__in=tenant_user_ids).delete()
        VirtualUserOwnerRelation.objects.filter(
            Q(tenant_user_id__in=tenant_user_ids) | Q(owner_id__in=tenant_user_ids)
        ).delete()
        TenantUserCustomField.objects.filter(tenant_id=tenant_id).delete()
        TenantUserValidityPeriodConfig.objects.get(tenant_id=tenant_id).delete()
        TenantUserDisplayNameExpressionConfig.objects.get(tenant_id=tenant_id).delete()
        TenantManager.objects.filter(tenant_id=tenant_id).delete()
        CollaborationStrategy.objects.filter(Q(source_tenant_id=tenant_id) | Q(target_tenant_id=tenant_id)).delete()
        idps = Idp.objects.filter(owner_tenant_id=tenant_id)
        idp_ids = list(idps.values_list("id", flat=True))
        IdpSensitiveInfo.objects.filter(idp_id__in=idp_ids).delete()
        idps.delete()
        data_sources = DataSource.objects.filter(owner_tenant_id=tenant_id)
        for data_source in data_sources:
            delete_data_source_and_related_resources(data_source)
        TenantUserIDRecord.objects.filter(tenant_id=tenant_id).delete()
        TenantDepartmentIDRecord.objects.filter(tenant_id=tenant_id).delete()
        TenantUserIDGenerateConfig.objects.filter(target_tenant_id=tenant_id).delete()
        TenantCommonVariable.objects.filter(tenant_id=tenant_id).delete()
        Tenant.objects.filter(id=tenant_id).delete()


def delete_data_source_and_related_resources(data_source: DataSource):
    TenantDepartment.objects.filter(data_source=data_source).delete()
    TenantUser.objects.filter(data_source=data_source).delete()
    TenantUserIDGenerateConfig.objects.filter(data_source=data_source).delete()
    TenantUserIDRecord.objects.filter(data_source=data_source).delete()
    TenantDepartmentIDRecord.objects.filter(data_source=data_source).delete()
    DataSourceDepartmentUserRelation.objects.filter(data_source=data_source).delete()
    DataSourceDepartmentRelation.objects.filter(data_source=data_source).delete()
    DataSourceDepartment.objects.filter(data_source=data_source).delete()
    DataSourceUserLeaderRelation.objects.filter(data_source=data_source).delete()
    DataSourceUser.objects.filter(data_source=data_source).delete()
    DepartmentRelationMPTTTree.objects.filter(data_source=data_source).delete()
    DataSourceSensitiveInfo.objects.filter(data_source=data_source).delete()
    data_source.delete()
