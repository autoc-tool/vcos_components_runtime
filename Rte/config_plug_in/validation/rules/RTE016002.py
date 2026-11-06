# This Python file uses the following encoding: utf-8
############################################################################
# Copyright (c) 2025 Li Auto Inc. and its affiliates
# Licensed under the Apache License, Version 2.0(the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############################################################################
from func_module.validation.common.basic_rule import BasicRule, timing_decorator
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData
from basic_func_module.autosar_utils.utils import (get_definition_ref, get_value_ref, get_numerical_param_value,
                                              get_annotations, get_short_name)


# 检查调度表是否是最新的状态，防止调度表未更新导致编译错误
class Rte016002Rule(BasicRule):
    ruleset_name = "RTE016002"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Schedule table should be updated after creating task or task mapping."
        self.rte_common_data = rte_common_data
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False

        return True

    def _get_bsw_task_info(self, rte_task_info, container, ib_class):
        ib_module_name = get_short_name(container)
        if ib_module_name not in ib_class:
            return
        for sub_con in getattr(getattr(container, 'SUB_CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
            if 'RteBswEventToTaskMapping' not in get_definition_ref(sub_con):
                continue
            ref_params = getattr(getattr(sub_con, 'REFERENCE_VALUES', None), 'ECUC_REFERENCE_VALUE', [])
            task_ref, os_ev_ref, bsw_ev_ref = "", "", []
            for ref_param in ref_params:
                def_ref = get_definition_ref(ref_param)
                if def_ref.endswith('RteBswEventRef'):
                    bsw_ev_ref.append(get_value_ref(ref_param))
                elif def_ref.endswith('RteBswUsedOsEventRef'):
                    os_ev_ref = get_value_ref(ref_param)
                elif def_ref.endswith('RteBswMappedToTaskRef'):
                    task_ref = get_value_ref(ref_param)
            if not task_ref or not os_ev_ref:
                continue
            for bsw_ev in bsw_ev_ref:
                event_obj = ib_class[ib_module_name].find(bsw_ev)
                if event_obj and 'BSW-TIMING-EVENT' == event_obj.get_tag():
                    task_name = task_ref.split("/")[-1]
                    rte_task_info.setdefault(task_name, set())
                    rte_task_info[task_name].add(os_ev_ref.split("/")[-1])

    def _get_swc_task_info(self, rte_task_info, container, asw_class):
        for sub_con in getattr(getattr(container, 'SUB_CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
            if 'RteEventToTaskMapping' not in get_definition_ref(sub_con):
                continue
            ref_params = getattr(getattr(sub_con, 'REFERENCE_VALUES', None), 'ECUC_REFERENCE_VALUE', [])
            task_ref, os_ev_ref, rte_ev_ref = "", "", []
            for ref_param in ref_params:
                def_ref = get_definition_ref(ref_param)
                if def_ref.endswith('RteEventRef'):
                    rte_ev_ref.append(get_value_ref(ref_param))
                elif def_ref.endswith('RteUsedOsEventRef'):
                    os_ev_ref = get_value_ref(ref_param)
                elif def_ref.endswith('RteMappedToTaskRef'):
                    task_ref = get_value_ref(ref_param)
            if not task_ref or not os_ev_ref:
                continue
            for swc_ev in rte_ev_ref:
                event_obj = asw_class.find(swc_ev)
                if event_obj and 'TIMING-EVENT' == event_obj.get_tag():
                    task_name = task_ref.split("/")[-1]
                    rte_task_info.setdefault(task_name, set())
                    rte_task_info[task_name].add(os_ev_ref.split("/")[-1])

    def get_cyclic_event_in_task_mapping(self, rte_ecuc_class, asw_class, ib_class):
        rte_task_info = {}
        for ar_pack in getattr(getattr(rte_ecuc_class, 'AR_PACKAGES', None), 'AR_PACKAGE', []):
            for containers in getattr(getattr(ar_pack, 'ELEMENTS', None), 'ECUC_MODULE_CONFIGURATION_VALUES', []):
                for container in getattr(getattr(containers, 'CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
                    container_def = get_definition_ref(container)
                    if container_def.endswith('/RteBswModuleInstance'):
                        self._get_bsw_task_info(rte_task_info, container, ib_class)
                    elif container_def.endswith('/RteSwComponentInstance'):
                        self._get_swc_task_info(rte_task_info, container, asw_class)
        return rte_task_info

    def get_cyclic_event_in_schedule_table(self, os_ecuc_class):
        sch_tab_event_settings = {}
        for ar_pack in getattr(getattr(os_ecuc_class, 'AR_PACKAGES', None), 'AR_PACKAGE', []):
            for containers in getattr(getattr(ar_pack, 'ELEMENTS', None), 'ECUC_MODULE_CONFIGURATION_VALUES', []):
                for container in getattr(getattr(containers, 'CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
                    if not get_definition_ref(container).endswith("/OsScheduleTable"):
                        continue
                    # can not be generated by task mapping common post
                    annotations = get_annotations(container)
                    if annotations and 'IsAutomatic' in get_annotations(container):
                        continue
                    # repeating must be checked
                    repeating_checked = False
                    num_params = getattr(getattr(container, 'PARAMETER_VALUES', None), 'ECUC_NUMERICAL_PARAM_VALUE', [])
                    for param in num_params:
                        if get_definition_ref(param).endswith('/OsScheduleTableRepeating'):
                            repeating_checked = get_numerical_param_value(param)
                            break
                    if not repeating_checked:
                        continue

                    for sub_con in getattr(getattr(container, 'SUB_CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
                        if not get_definition_ref(sub_con).endswith('OsScheduleTableExpiryPoint'):
                            continue
                        for ev_setting in getattr(getattr(sub_con, 'SUB_CONTAINERS', None), 'ECUC_CONTAINER_VALUE', []):
                            if not get_definition_ref(ev_setting).endswith('OsScheduleTableEventSetting'):
                                continue
                            refs = getattr(getattr(ev_setting, 'REFERENCE_VALUES', None), 'ECUC_REFERENCE_VALUE', [])
                            task_name, event_name = "", ""
                            for ref_param in refs:
                                def_ref = get_definition_ref(ref_param)
                                if def_ref.endswith('/OsScheduleTableSetEventTaskRef'):
                                    task_ref = get_value_ref(ref_param)
                                    task_name = task_ref.split("/")[-1] if task_ref else ""
                                elif def_ref.endswith('/OsScheduleTableSetEventRef'):
                                    event_ref = get_value_ref(ref_param)
                                    event_name = event_ref.split("/")[-1] if event_ref else ""
                            if task_name and event_name:
                                sch_tab_event_settings.setdefault(task_name, set())
                                sch_tab_event_settings[task_name].add(event_name)
        return sch_tab_event_settings

    @timing_decorator
    def validation_run(self):
        bsw_class = self.rte_common_data.bsw_ecuc_autosar_dict
        asw_class = self.rte_common_data.asw_autosar_dict
        ib_class = self.rte_common_data.internal_behavior_autosar_dict
        sch_tab_task_info = self.get_cyclic_event_in_schedule_table(bsw_class["Os"])
        rte_task_info = self.get_cyclic_event_in_task_mapping(bsw_class["Rte"], asw_class, ib_class)

        manual_solve_list = ["please update schedule table in OS Configuration manually."]
        for task_name, sch_tab_ev_set in sch_tab_task_info.items():
            task_name = task_name
            rte_ev_set = rte_task_info.get(task_name, set())
            if sch_tab_ev_set != rte_ev_set:
                message = f"schedule table event list: {sch_tab_ev_set}, task mapping event list: {rte_ev_set}"
                param_path = f"/ActiveEcuC/Os/{task_name}"
                self.vlog(self.validation_code,
                          self.validation_summary,
                          message,
                          param_path,
                          "fail",
                          manual_solve_list=manual_solve_list)
                break
