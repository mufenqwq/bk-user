<template>
  <bk-dialog
    :is-show="isShow"
    :width="640"
    render-directive="if"
    :quick-close="false"
    :before-close="handleBeforeClose"
    @closed="handleClosed"
  >
    <template #header>
      <div class="login-config-header">
        <span class="login-config-title">{{ $t('登录配置') }}</span>
        <span class="login-config-subtitle">{{ dataSourceName }}</span>
      </div>
    </template>
    <div class="login-config-body" :class="{ 'is-loading': isLoading }" v-bkloading="{ isLoading }">
      <bk-form ref="formRef" form-type="vertical" :model="formData">
        <bk-form-item :label="$t('登录方式')" required>
          <div class="login-options">
            <bk-popover
              v-for="opt in loginOptions"
              :key="opt.key"
              :disabled="!opt.tooltip"
              :content="opt.tooltip"
              placement="top">
              <bk-checkbox
                class="login-option"
                :model-value="opt.checked"
                :disabled="opt.disabled"
                @change="(value: boolean) => handleCheckChange(opt, value)"
              >
                {{ opt.label }}
              </bk-checkbox>
            </bk-popover>
          </div>
        </bk-form-item>
        <template v-if="checkedTypeIds.length">
          <!-- 登录认证匹配标签与卡片保持平级：bkui 的 required 星号是后代选择器，嵌套会渗透给卡片内的字段标签 -->
          <bk-form-item class="!mt-[16px] !mb-[12px]" :label="$t('登录认证匹配')" required />
          <!-- 每个勾选的类型登录各一张匹配卡片，生效范围固定为当前数据源 -->
          <div class="login-match-list">
            <DataSourceMatchCard
              v-for="(pluginId, index) in checkedTypeIds"
              :key="pluginId"
              :data-source-id="props.dataSourceId"
              :data-source-name="dataSourceName"
              :rule-index="index"
              :field-compare-rules="formData.data_source_match_rules[index].field_compare_rules"
              :field-options="fieldOptions"
              @remove="handleRemoveCard(pluginId)"
              @add="(i) => handleAddItem(formData.data_source_match_rules[index].field_compare_rules, i)"
              @delete="(i) => handleDeleteItem(index, formData.data_source_match_rules[index].field_compare_rules, i)"
              @change="handleChange"
            />
          </div>
        </template>
      </bk-form>
    </div>
    <template #footer>
      <div class="login-config-footer">
        <bk-button
          theme="primary"
          :loading="btnLoading"
          @click="handleConfirm"
        >
          {{ $t('确认') }}
        </bk-button>
        <bk-button @click="handleCancel">
          {{ $t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
import { Message } from 'bkui-vue';
import { computed, inject, ref, watch } from 'vue';

import DataSourceMatchCard from '../auth-config/DataSourceMatchCard.vue';

import { useCustomPlugin } from '@/hooks';
import {
  getFields,
  getIdps,
  getIdpsDetails,
  getIdpsPlugins,
  postIdps,
  putIdps,
} from '@/http';
import { t } from '@/language/index';

interface IProps {
  isShow: boolean;
  dataSourceId: number;
  /** 数据源名称（弹窗副标题、匹配卡片标题） */
  dataSourceName: string;
  /** 仅本地数据源可勾选账密登录 */
  isLocal: boolean;
}

const props = defineProps<IProps>();
const editLeaveBefore = inject<() => Promise<boolean>>('editLeaveBefore');
const emit = defineEmits<{
  'update:isShow': [value: boolean];
  /** 保存成功，父级据此刷新登录方式标签 */
  success: [];
}>();

interface ILoginOption {
  key: string;
  label: string;
  checked: boolean;
  disabled: boolean;
  tooltip: string;
}

interface IMatchRule {
  data_source_id: number;
  field_compare_rules: { source_field: string; target_field: string }[];
}

interface IIdpDetail {
  id: string;
  name: string;
  status: string;
  plugin_config: Record<string, unknown>;
  data_source_match_rules: IMatchRule[];
}

const isLoading = ref(true);
const btnLoading = ref(false);
const formRef = ref();

const idpPlugins = ref<{ id: string; name: string }[]>([]);
const existingIdps = ref(new Map<string, { id: string }>());
const typeDetails = ref<Record<string, IIdpDetail>>({});
const localIdpDetail = ref<IIdpDetail | null>(null);
const builtinFields = ref([]);
const customFields = ref([]);

/** 已勾选的类型登录（非账密），顺序与匹配表单的规则顺序一致 */
const checkedTypeIds = ref<string[]>([]);
/** 各类型登录的匹配规则，勾选期间保留编辑内容 */
const ruleStore = ref<Record<string, IMatchRule>>({});

const localChecked = ref(false);

const formData = ref({ data_source_match_rules: [] as IMatchRule[] });
const dataSourceList = ref([]);

const fieldOptions = computed(() => [
  ...(builtinFields.value as Array<{ id: number; name: string }>).map(item => ({ key: item.id, name: item.name, type: t('内置') })),
  ...(customFields.value as Array<{ id: number; name: string }>).map(item => ({ key: item.id, name: item.name, type: t('自定义') })),
]);

const { handleChange, handleAddItem, handleDeleteItem } = useCustomPlugin(formData, dataSourceList);

const isTypeConfigured = (pluginId: string) => !!typeDetails.value[pluginId]?.data_source_match_rules
  .some(rule => rule.data_source_id === props.dataSourceId);
const localIdpConfigured = computed(() => !!localIdpDetail.value?.data_source_match_rules
  .some(rule => rule.data_source_id === props.dataSourceId));

// 每次打开弹窗按已覆盖情况重建勾选态，避免上次取消关闭残留的编辑
const resetCheckedState = () => {
  localChecked.value = false;
  ruleStore.value = {};
  checkedTypeIds.value = Object.keys(typeDetails.value)
    .filter(id => isTypeConfigured(id));
};

const loginOptions = computed<ILoginOption[]>(() => idpPlugins.value.map((plugin) => {
  if (plugin.id === 'local') {
    const option: ILoginOption = {
      key: 'local',
      label: t('使用账密登录'),
      checked: localChecked.value || localIdpConfigured.value,
      disabled: !props.isLocal,
      tooltip: '',
    };
    if (!props.isLocal) {
      option.tooltip = t('仅本地数据源支持账密登录');
    }
    return option;
  }
  const exists = existingIdps.value.has(plugin.id);
  const option: ILoginOption = {
    key: plugin.id,
    label: t('使用x登录', { name: plugin.name }),
    checked: checkedTypeIds.value.includes(plugin.id) || isTypeConfigured(plugin.id),
    disabled: !exists,
    tooltip: '',
  };
  if (!exists) {
    option.tooltip = t('尚未创建该认证源，请前往登录设置创建');
  }
  return option;
}));

const handleCheckChange = (opt: ILoginOption, value: boolean) => {
  if (opt.key === 'local') {
    localChecked.value = value;
    return;
  }
  if (value) {
    checkedTypeIds.value = [...checkedTypeIds.value, opt.key];
  } else {
    checkedTypeIds.value = checkedTypeIds.value.filter(id => id !== opt.key);
  }
};

// 卡片关闭等同于取消勾选对应登录方式
const handleRemoveCard = (pluginId: string) => {
  checkedTypeIds.value = checkedTypeIds.value.filter(id => id !== pluginId);
};

const handleConfirm = async () => {
  btnLoading.value = true;
  try {
    // 校验：append 与已配置勾选的卡片都要通过，纯编辑已配置卡片（清空字段）也能拦住
    const pendingTypeIds = checkedTypeIds.value
      .filter(id => existingIdps.value.has(id));
    if (pendingTypeIds.length) {
      await formRef.value?.validate();
    }
    // 追加：未配置且当前勾选的类型登录
    const appendTypeIds = pendingTypeIds.filter(id => !isTypeConfigured(id));
    for (const pluginId of appendTypeIds) {
      const detail = typeDetails.value[pluginId];
      await putIdps({
        id: detail.id,
        name: detail.name,
        status: detail.status,
        plugin_config: detail.plugin_config,
        data_source_match_rules: [
          ...detail.data_source_match_rules,
          { data_source_id: props.dataSourceId, field_compare_rules: ruleStore.value[pluginId].field_compare_rules },
        ],
      });
      // 保存成功后同步本地详情，避免重开弹窗按陈旧数据误判为未配置而重复追加
      detail.data_source_match_rules.push({
        data_source_id: props.dataSourceId,
        field_compare_rules: ruleStore.value[pluginId].field_compare_rules,
      });
    }
    // 已配置且保持勾选的：卡片编辑在副本上，确认时写回详情再整体保存
    for (const pluginId of pendingTypeIds.filter(id => isTypeConfigured(id))) {
      const detail = typeDetails.value[pluginId];
      const target = detail.data_source_match_rules
        .find(rule => rule.data_source_id === props.dataSourceId);
      Object.assign(target, ruleStore.value[pluginId]);
      await putIdps({
        id: detail.id,
        name: detail.name,
        status: detail.status,
        plugin_config: detail.plugin_config,
        data_source_match_rules: detail.data_source_match_rules,
      });
    }
    // 移除：已配置但被取消勾选的类型登录
    const removeTypeIds = Object.keys(typeDetails.value)
      .filter(id => isTypeConfigured(id) && !checkedTypeIds.value.includes(id));
    for (const pluginId of removeTypeIds) {
      const detail = typeDetails.value[pluginId];
      await putIdps({
        id: detail.id,
        name: detail.name,
        status: detail.status,
        plugin_config: detail.plugin_config,
        data_source_match_rules: detail.data_source_match_rules
          .filter(rule => rule.data_source_id !== props.dataSourceId),
      });
    }
    if (props.isLocal) {
      const configured = localIdpConfigured.value;
      const localRule = {
        data_source_id: props.dataSourceId,
        // 本地账密的字段匹配规则后端约定写死 id -> id
        field_compare_rules: [{ source_field: 'id', target_field: 'id' }],
      };
      if (localChecked.value && !configured) {
        if (localIdpDetail.value) {
          await putIdps({
            id: localIdpDetail.value.id,
            name: localIdpDetail.value.name,
            status: localIdpDetail.value.status,
            plugin_config: localIdpDetail.value.plugin_config,
            data_source_match_rules: [
              ...localIdpDetail.value.data_source_match_rules,
              localRule,
            ],
          });
          // 同步本地详情，保持与后端一致
          localIdpDetail.value.data_source_match_rules.push(localRule);
        } else {
          await postIdps({
            name: idpPlugins.value.find(plugin => plugin.id === 'local')?.name || 'local',
            status: 'enabled',
            plugin_id: 'local',
            // local 认证源后端忽略 plugin_config，按匹配规则自动生成
            plugin_config: {},
            data_source_match_rules: [localRule],
          });
          // 新建后本地无详情，重拉一次，避免下次打开误判为未配置而重复创建
          const listRes = await getIdps('');
          const localItem = (listRes.data || []).find(item => item.plugin.id === 'local');
          if (localItem) {
            const detailRes = await getIdpsDetails(localItem.id);
            localIdpDetail.value = detailRes.data;
          }
        }
      } else if (!localChecked.value && configured && localIdpDetail.value) {
        await putIdps({
          id: localIdpDetail.value.id,
          name: localIdpDetail.value.name,
          status: localIdpDetail.value.status,
          plugin_config: localIdpDetail.value.plugin_config,
          data_source_match_rules: localIdpDetail.value.data_source_match_rules
            .filter(rule => rule.data_source_id !== props.dataSourceId),
        });
      }
    }
    Message({ theme: 'success', message: t('保存成功') });
    window.changeInput = false;
    emit('success');
    emit('update:isShow', false);
  } catch (error) {
    console.error(error);
  } finally {
    btnLoading.value = false;
  }
};

// 关闭前有未保存编辑时按项目惯例弹离开确认（main.ts 全局注入），X/esc 与取消按钮共用
const handleBeforeClose = async () => {
  let enableLeave = true;
  if (window.changeInput) {
    enableLeave = await editLeaveBefore();
  }
  if (enableLeave) {
    window.changeInput = false;
  }
  return enableLeave;
};

const handleCancel = async () => {
  if (await handleBeforeClose()) {
    emit('update:isShow', false);
  }
};

// 勾选集合变化时同步表单规则数组；已配置的存详情规则的副本，卡片编辑只落在副本上，取消关闭天然回滚
watch(checkedTypeIds, (ids) => {
  formData.value.data_source_match_rules = ids.map((id) => {
    if (!ruleStore.value[id]) {
      const existing = typeDetails.value[id]?.data_source_match_rules
        ?.find(rule => rule.data_source_id === props.dataSourceId);
      ruleStore.value[id] = existing
        ? JSON.parse(JSON.stringify(existing))
        : {
          data_source_id: props.dataSourceId,
          field_compare_rules: [{ target_field: '', source_field: '' }],
        };
    }
    return ruleStore.value[id];
  });
}, { immediate: true });

// 首次打开才请求详情，避免列表页挂载即拉全部认证源详情
const detailsLoaded = ref(false);
const loadDetails = async () => {
  try {
    isLoading.value = true;
    const [pluginsRes, idpsRes, fieldsRes] = await Promise.all([
      getIdpsPlugins(),
      getIdps(''),
      getFields(),
    ]);
    idpPlugins.value = pluginsRes.data || [];
    existingIdps.value = new Map((idpsRes.data || []).map(item => [item.plugin.id, item]));
    builtinFields.value = fieldsRes.data?.builtin_fields || [];
    customFields.value = fieldsRes.data?.custom_fields || [];

    // 已存在的认证源取详情：判断当前数据源是否已在其生效范围，保存时透传脱敏凭证（后端回填）
    const detailRequests = (idpsRes.data || []).map(async (item) => {
      const detailRes = await getIdpsDetails(item.id);
      if (item.plugin.id === 'local') {
        localIdpDetail.value = detailRes.data;
      } else {
        typeDetails.value[item.plugin.id] = detailRes.data;
      }
    });
    await Promise.all(detailRequests);
    detailsLoaded.value = true;
    resetCheckedState();
  } catch (error) {
    console.error(error);
  } finally {
    isLoading.value = false;
  }
};

watch(() => props.isShow, (val) => {
  if (!val) return;
  if (detailsLoaded.value) {
    resetCheckedState();
  } else {
    loadDetails();
  }
});
</script>

<style lang="less" scoped>
.login-config-header {
  display: flex;
  align-items: baseline;

  .login-config-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--title-color);
  }

  .login-config-subtitle {
    margin-left: 12px;
    padding-left: 12px;
    border-left: 1px solid var(--border-color);
    font-size: 14px;
    color: var(--gray-color);
  }
}

.login-config-body {
  text-align: left;

  .login-options {
    display: flex;
    gap: 24px;
  }

  .login-match-list {
    display: flex;
    flex-direction: column;
  }

  // loading 时撑出转圈空间，内容态高度自适应
  &.is-loading {
    min-height: 200px;
  }
}

.login-config-footer {
  text-align: right;
}
</style>
