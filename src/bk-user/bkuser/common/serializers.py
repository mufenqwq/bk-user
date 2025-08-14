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
from typing import List

from django.utils.translation import gettext_lazy as _
from rest_framework import fields, serializers
from rest_framework.fields import empty


class StringArrayField(fields.CharField):
    """String representation of an array field"""

    default_error_messages = {
        "max_items": _("至多包含 {max_items} 个对象。"),
        "min_items": _("至少包含 {min_items} 个对象。"),
        "max_item_length": _("每个对象长度不能超过 {max_item_length} 个字符。"),
        "min_item_length": _("每个对象长度不能小于 {min_item_length} 个字符。"),
    }

    def __init__(
        self,
        min_items: int | None = None,
        max_items: int | None = None,
        min_item_length: int | None = None,
        max_item_length: int | None = None,
        delimiter: str = ",",
        **kwargs,
    ):
        self.min_items = min_items
        self.max_items = max_items
        self.min_item_length = min_item_length
        self.max_item_length = max_item_length
        self.delimiter = delimiter

        super().__init__(**kwargs)

    def run_validation(self, data=empty):
        data = super().run_validation(data)

        item_cnt = len(data)
        if self.min_items is not None and item_cnt < self.min_items:
            self.fail("min_items", min_items=self.min_items)

        if self.max_items is not None and item_cnt > self.max_items:
            self.fail("max_items", max_items=self.max_items)

        for item in data:
            if self.min_item_length is not None and len(item) < self.min_item_length:
                self.fail("min_item_length", min_item_length=self.min_item_length)
            if self.max_item_length is not None and len(item) > self.max_item_length:
                self.fail("max_item_length", max_item_length=self.max_item_length)

        return data

    def to_internal_value(self, data) -> List[str]:
        # convert string to list
        data = super().to_internal_value(data)
        return [x.strip() for x in data.split(self.delimiter) if x]


class PasswordRuleSerializer(serializers.Serializer):
    """密码规则序列化器"""

    # --- 长度限制类 ---
    min_length = fields.IntegerField(help_text="密码最小长度")
    max_length = fields.IntegerField(help_text="密码最大长度")
    # --- 字符限制类 ---
    contain_lowercase = fields.BooleanField(help_text="必须包含小写字母")
    contain_uppercase = fields.BooleanField(help_text="必须包含大写字母")
    contain_digit = fields.BooleanField(help_text="必须包含数字")
    contain_punctuation = fields.BooleanField(help_text="必须包含特殊字符（标点符号）")
    # --- 连续性限制类 ---
    not_continuous_count = fields.IntegerField(help_text="密码不允许连续 N 位出现")
    not_keyboard_order = fields.BooleanField(help_text="不允许键盘序")
    not_continuous_letter = fields.BooleanField(help_text="不允许连续字母序")
    not_continuous_digit = fields.BooleanField(help_text="不允许连续数字序")
    not_repeated_symbol = fields.BooleanField(help_text="重复字母，数字，特殊字符")
    # --- 规则提示 ---
    rule_tips = fields.ListField(help_text="用户密码规则提示", child=fields.CharField(), source="tips")
