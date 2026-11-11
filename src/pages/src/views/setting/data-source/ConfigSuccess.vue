<template>
  <div class="success-wrapper" v-bkloading="{ isLoading }">
    <div class="content">
      <i class="user-icon icon-duihao-2" />
      <p class="title">{{ title }}</p>
      <div class="login-options mt-[24px]" v-if="isCreate && loginOptions.length">
        <bk-popover
          v-for="opt in loginOptions"
          :key="opt.key"
          :disabled="!opt.tooltip"
          :content="opt.tooltip"
          placement="top">
          <bk-checkbox
            class="login-option mr-[24px]"
            :model-value="opt.checked"
            :disabled="opt.disabled"
            @change="(value: boolean) => handleCheckChange(opt, value)"
          >
            {{ opt.label }}
          </bk-checkbox>
        </bk-popover>
      </div>
      <!-- 快捷勾选后展示各登录方式的匹配规则配置，生效范围固定为当前新建的数据源 -->
      <bk-form
        v-if="checkedTypeIds.length"
        ref="formRef"
        class="login-match-form"
        form-type="vertical"
        :model="formData">
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
        >
          <template #label>
            <bk-form-item class="!mb-[8px] match-label-item" :label="$t('登录认证匹配')" required />
          </template>
        </DataSourceMatchCard>
      </bk-form>
      <div class="mt-[24px]">
        <bk-button
          v-if="!isLocal"
          class="mr-[8px]"
          theme="primary"
          @click="handleOperate('dataSource', true)"
        >
          {{ $t('立即同步') }}
        </bk-button>
        <bk-button
          class="mr-[8px]"
          theme="primary"
          @click="handleOperate('login')"
        >
          {{ $t('登录配置') }}
        </bk-button>
        <bk-button @click="handleOperate('organization')">
          {{ $t('查看组织架构') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Message } from 'bkui-vue';
import { computed, onMounted, ref, watch } from 'vue';

import DataSourceMatchCard from '../auth-config/DataSourceMatchCard.vue';

import { useCustomPlugin } from '@/hooks';
import {
  getDataSourceDetails,
  getFields,
  getIdps,
  getIdpsDetails,
  getIdpsPlugins,
  postIdps,
  putIdps,
} from '@/http';
import { postOperationsSync } from '@/http/dataSourceFiles';
import { t } from '@/language/index';
import router from '@/router';

interface IProps {
  title: string;
  dataSourceId: number;
  /** 本地数据源不展示「立即同步」，账密登录快捷勾选仅本地数据源可用，由父组件按数据源类型传入 */
  isLocal?: boolean;
  /** 是否为新建成功；更新成功沿用原有展示，不出现认证源快捷配置 */
  isCreate?: boolean;
}

const props = withDefaults(defineProps<IProps>(), {
  title: '',
  isLocal: false,
  isCreate: false,
});

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

const idpPlugins = ref<{ id: string; name: string }[]>([]);
const existingIdps = ref(new Map<string, { id: string }>());
const dataSourceName = ref('');
const builtinFields = ref([]);
const customFields = ref([]);

/** 已存在认证源的详情：判断当前数据源是否已在其生效范围，保存时透传脱敏凭证（后端回填） */
const typeDetails = ref<Record<string, IIdpDetail>>({});
const localIdpDetail = ref<IIdpDetail | null>(null);

/** 已勾选的类型登录（非账密），顺序与匹配表单的规则顺序一致 */
const checkedTypeIds = ref<string[]>([]);
/** 各类型登录的匹配规则，勾选期间保留编辑内容 */
const ruleStore = ref<Record<string, IMatchRule>>({});

const localChecked = ref(false);

const formData = ref({ data_source_match_rules: [] as IMatchRule[] });
const dataSourceList = ref([]);
const formRef = ref();

const fieldOptions = computed(() => [
  ...(builtinFields.value as Array<{ id: number; name: string }>).map(item => ({ key: item.id, name: item.name, type: t('内置') })),
  ...(customFields.value as Array<{ id: number; name: string }>).map(item => ({ key: item.id, name: item.name, type: t('自定义') })),
]);

const { handleChange, handleAddItem, handleDeleteItem } = useCustomPlugin(formData, dataSourceList);

// 勾选集合变化时同步表单规则数组，规则对象按插件 id 复用，避免已编辑内容丢失
watch(checkedTypeIds, (ids) => {
  formData.value.data_source_match_rules = ids.map((id) => {
    if (!ruleStore.value[id]) {
      ruleStore.value[id] = {
        data_source_id: props.dataSourceId,
        field_compare_rules: [{ target_field: '', source_field: '' }],
      };
    }
    return ruleStore.value[id];
  });
}, { immediate: true });

/** 类型登录：当前数据源已在认证源生效范围内视为已配置 */
const isTypeConfigured = (pluginId: string) => !!typeDetails.value[pluginId]?.data_source_match_rules
  .some(rule => rule.data_source_id === props.dataSourceId);
const localIdpConfigured = computed(() => !!localIdpDetail.value?.data_source_match_rules
  .some(rule => rule.data_source_id === props.dataSourceId));

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
  // 勾选/取消勾选本身也是需要随跳转保存的编辑意图
  window.changeInput = true;
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
  window.changeInput = true;
  checkedTypeIds.value = checkedTypeIds.value.filter(id => id !== pluginId);
};

// 三个操作按钮离开本页前都会先保存快捷认证源配置（见 saveBeforeLeave）
const handleSave = async () => {
  btnLoading.value = true;
  try {
    const pendingTypeIds = checkedTypeIds.value
      .filter(id => existingIdps.value.has(id));
    if (pendingTypeIds.length) {
      await formRef.value?.validate();
    }
    let savedAny = false;
    for (const pluginId of pendingTypeIds) {
      const detail = typeDetails.value[pluginId];
      const target = detail.data_source_match_rules
        .find(rule => rule.data_source_id === props.dataSourceId);
      // 已在生效范围的走整体写回（编辑过的规则覆盖），未配置的追加，避免重复规则
      const rules = target
        ? detail.data_source_match_rules
        : [...detail.data_source_match_rules, {
          data_source_id: props.dataSourceId,
          field_compare_rules: ruleStore.value[pluginId].field_compare_rules,
        }];
      if (target) {
        Object.assign(target, ruleStore.value[pluginId]);
      }
      await putIdps({
        id: detail.id,
        name: detail.name,
        status: detail.status,
        plugin_config: detail.plugin_config,
        data_source_match_rules: rules,
      });
      savedAny = true;
    }
    let localSaved = false;
    if (props.isLocal && localChecked.value && !localIdpConfigured.value) {
      const rule = {
        data_source_id: props.dataSourceId,
        // 本地账密的字段匹配规则后端约定写死 id -> id
        field_compare_rules: [{ source_field: 'id', target_field: 'id' }],
      };
      if (localIdpDetail.value) {
        await putIdps({
          id: localIdpDetail.value.id,
          name: localIdpDetail.value.name,
          status: localIdpDetail.value.status,
          plugin_config: localIdpDetail.value.plugin_config,
          data_source_match_rules: [
            ...localIdpDetail.value.data_source_match_rules,
            rule,
          ],
        });
        // 同步本地详情，保持与后端一致
        localIdpDetail.value.data_source_match_rules.push(rule);
      } else {
        await postIdps({
          name: idpPlugins.value.find(plugin => plugin.id === 'local')?.name || 'local',
          status: 'enabled',
          plugin_id: 'local',
          // local 认证源后端忽略 plugin_config，按匹配规则自动生成
          plugin_config: {},
          data_source_match_rules: [rule],
        });
      }
      localSaved = true;
    }
    window.changeInput = false;
    if (savedAny || localSaved) {
      Message({ theme: 'success', message: t('保存成功') });
    }
  } catch (error) {
    console.error(error);
  } finally {
    btnLoading.value = false;
  }
};

// 有未保存编辑时先保存；保存失败（如校验不通过）返回 false 留在本页
const saveBeforeLeave = async () => {
  if (!window.changeInput) {
    return true;
  }
  await handleSave();
  return !window.changeInput;
};

// 三个操作按钮共用：先保存快捷认证源配置，再跳转；needSync 为 true 时先触发数据同步
const handleOperate = async (routeName: string, needSync = false) => {
  if (!await saveBeforeLeave()) {
    return;
  }
  if (needSync) {
    const res = await postOperationsSync(props.dataSourceId);
    Message({ theme: res.data.status, message: res.data.summary });
  }
  router.push({ name: routeName });
};

onMounted(async () => {
  // 更新成功沿用原有展示，无需加载快捷配置相关数据
  if (!props.isCreate) {
    isLoading.value = false;
    return;
  }
  try {
    isLoading.value = true;
    const [pluginsRes, idpsRes, fieldsRes, dsDetailRes] = await Promise.all([
      getIdpsPlugins(),
      getIdps(''),
      getFields(),
      getDataSourceDetails(props.dataSourceId),
    ]);
    idpPlugins.value = pluginsRes.data || [];
    existingIdps.value = new Map((idpsRes.data || []).map(item => [item.plugin.id, item]));
    dataSourceName.value = dsDetailRes.data?.name || '';
    builtinFields.value = fieldsRes.data?.builtin_fields || [];
    customFields.value = fieldsRes.data?.custom_fields || [];

    // 已存在的认证源取详情：保存时原样透传脱敏凭证（后端回填），并判断当前数据源是否已在其生效范围
    const detailRequests = (idpsRes.data || []).map(async (item) => {
      const detailRes = await getIdpsDetails(item.id);
      if (item.plugin.id === 'local') {
        localIdpDetail.value = detailRes.data;
      } else {
        typeDetails.value[item.plugin.id] = detailRes.data;
      }
    });
    await Promise.all(detailRequests);
  } catch (error) {
    console.error(error);
  } finally {
    isLoading.value = false;
  }
});
</script>

<style lang="less" scoped>
.success-wrapper {
  position: relative;
  width: 100%;
  height: calc(100vh - var(--header-height) - var(--breadcrumbs-height) - 32px);
  min-height: 400px;
  text-align: center;
  background: #fff;

  .content {
    position: absolute;
    top: 50%;
    left: 50%;
    // 固定为匹配卡片宽度：勾选/取消勾选时内容块宽度不变，避免水平居中位置跳动
    width: 560px;
    transform: translate(-50%, -50%);

    .icon-duihao-2 {
      font-size: 56px;
      color: #2DCB56;
    }

    .title {
      margin: 21px 0 6px;
      font-size: 16px;
      color: #000;
    }

    .login-options {
      text-align: center;
    }

    .login-match-form {
      width: 560px;
      margin-top: 16px;
      text-align: left;

      .match-label-item {
        :deep(.bk-form-label) {
          color: #4D4F56;
          font-size: 12px;
        }
      }
    }
  }
}
</style>
