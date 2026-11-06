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
import gc
from collections import defaultdict
from func_module.health_monitor.logger import logger
from basic_func_module.autosar_utils.autosar_util import AutosarUtil
from func_module.mapping.schedule_table_mapping import ScheduleTableManager
from basic_func_module.autosar_utils.utils import (
    get_short_name,
    get_definition_ref,
    get_value_ref,
    get_value,
    set_value_ref,
    set_value,
)


class OsManager:

    @classmethod
    def get_core_id(self, appl_name, core_ref, ecuc_autosar):
        core_id = None
        if not ecuc_autosar or not core_ref:
            return core_id
        core_def = ecuc_autosar.find(core_ref)
        if core_def is None:
            logger.error(f"{appl_name} OsApplicationCoreRef: {core_ref} not found!")
            return core_id
        parameter_values = getattr(getattr(core_def, "PARAMETER_VALUES", ""), "ECUC_NUMERICAL_PARAM_VALUE", [])
        for param_val in parameter_values:
            def_tag = get_definition_ref(param_val)
            if def_tag.endswith("EcucCoreId"):
                core_id = get_value(param_val)
                break
        return core_id

    @classmethod
    def get_appl_ref_dict(cls, container_value):
        ref_dict = defaultdict(list)
        for reference_values in container_value.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
            def_tag = get_definition_ref(reference_values)
            value_ref = get_value_ref(reference_values)
            if def_tag.endswith("OsAppTaskRef"):
                ref_dict["TaskRefs"].append(value_ref)
            elif def_tag.endswith("OsApplicationCoreRef"):
                ref_dict["CoreRef"] = value_ref
        return ref_dict

    @classmethod
    def get_os_task_autostart(cls, container_value):
        OsTaskAutostart = "FALSE"
        if not container_value.SUB_CONTAINERS:
            return OsTaskAutostart
        for sub_container_value in container_value.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
            def_tag = get_definition_ref(sub_container_value)
            if def_tag.endswith("OsTaskAutostart"):
                OsTaskAutostart = "TRUE"
                break
        return OsTaskAutostart

    @classmethod
    def get_os_task_dict(cls, os_autosar, ecuc_autosar, is_get_core_id=True):
        os_task_dict = {}
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        container_values = os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE
        for container_value in container_values:
            def_tag = get_definition_ref(container_value)
            if def_tag.endswith("OsTask"):
                task_name = get_short_name(container_value)
                task = os_task_dict.get(task_name)
                if task and task["Repeated"]:
                    logger.error(f"{task_name} Duplicate configuration!")
                    continue
                if task is None:
                    os_task_dict[task_name] = {}
                appl_name = os_task_dict[task_name].get("OsApplName")
                if appl_name is None:
                    appl_name = "<OsApp unassigned>"
                os_task_dict[task_name]["Repeated"] = True
                os_task_dict[task_name]["OsTaskName"] = task_name
                os_task_dict[task_name]["OsApplName"] = appl_name
                parameter_values = []
                parameter_values += container_value.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
                parameter_values += container_value.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
                for parameter_value in parameter_values:
                    def_tag = get_definition_ref(parameter_value)
                    if def_tag.endswith("OsTaskType"):
                        os_task_dict[task_name]["OsTaskType"] = get_value(parameter_value)
                    elif def_tag.endswith("OsTaskPriority"):
                        os_task_dict[task_name]["OsTaskPriority"] = get_value(parameter_value)
                os_task_dict[task_name]["OsTaskAutostart"] = cls.get_os_task_autostart(container_value)
            elif def_tag.endswith("OsApplication"):
                if not container_value.REFERENCE_VALUES:
                    continue
                appl_name = get_short_name(container_value)
                ref_dict = cls.get_appl_ref_dict(container_value)
                core_ref = ref_dict.get("CoreRef")
                core_id = cls.get_core_id(appl_name, core_ref, ecuc_autosar)
                if core_id is None and is_get_core_id:
                    logger.error(f"{appl_name} OsApplicationCoreRef: {core_ref} not found!")
                    continue
                task_refs = ref_dict.get("TaskRefs", [])
                for task_ref in task_refs:
                    if task_ref is None:
                        logger.error(f"{appl_name} OsAppTaskRef: {task_ref} not found!")
                        continue
                    task = os_autosar.find(task_ref)
                    if task is None:
                        logger.error(f"{appl_name} OsAppTaskRef: {task_ref} not found!")
                        continue
                    task_name = get_short_name(task)
                    if task_name not in os_task_dict:
                        os_task_dict[task_name] = {}
                    os_task_dict[task_name]["Repeated"] = False
                    os_task_dict[task_name]["OsApplName"] = appl_name
                    os_task_dict[task_name]["CoreId"] = core_id
        return os_task_dict

    @classmethod
    def get_os_appl_list(cls, os_autosar):
        os_appl_list = []
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        container_values = os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE
        for container_value in container_values:
            def_tag = get_definition_ref(container_value)
            if not def_tag.endswith("OsApplication"):
                continue

            if not container_value.REFERENCE_VALUES:
                continue
            appl_name = get_short_name(container_value)
            os_appl_list.append(appl_name)

        return os_appl_list

    @classmethod
    def get_os_alarm_event_set(cls, os_autosar):
        os_alarm_set = set()
        os_event_set = set()
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        for container_value in os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE:
            if not AutosarUtil.is_automatic(container_value):
                continue
            def_ref: str = get_definition_ref(container_value)
            if def_ref.endswith("OsAlarm"):
                os_alarm = container_value
                os_alarm_name = get_short_name(os_alarm)
                os_alarm_set.add(os_alarm_name)
            elif def_ref.endswith("OsEvent"):
                os_event = container_value
                os_event_name = get_short_name(os_event)
                os_event_set.add(os_event_name)
        return os_alarm_set, os_event_set

    # 保证event和alarm引用的唯一性，删除重复引用
    @classmethod
    def update_os_ref(cls, os_autosar):
        task_event_ref_dict = {}
        appl_alarm_ref_dict = {}

        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        for container_value in os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE:
            def_ref: str = get_definition_ref(container_value)
            if def_ref.endswith("OsTask"):
                reference_values = getattr(container_value.REFERENCE_VALUES, "ECUC_REFERENCE_VALUE", [])
                i = 0
                while i < len(reference_values):
                    reference_value = reference_values[i]
                    def_ref = get_definition_ref(reference_value)
                    if not def_ref.endswith("OsTaskEventRef"):
                        i += 1
                        continue
                    value_ref = get_value_ref(reference_value)
                    if value_ref in ("<empty>", None, ""):
                        i += 1
                        continue
                    if value_ref not in task_event_ref_dict:
                        task_event_ref_dict[value_ref] = reference_value
                        i += 1
                    else:
                        # 保证os中event引用的唯一性
                        del reference_values[i]
            elif def_ref.endswith("OsApplication"):
                reference_values = getattr(container_value.REFERENCE_VALUES, "ECUC_REFERENCE_VALUE", [])
                i = 0
                while i < len(reference_values):
                    reference_value = reference_values[i]
                    def_ref = get_definition_ref(reference_value)
                    if not def_ref.endswith("OsAppAlarmRef"):
                        i += 1
                        continue
                    value_ref = get_value_ref(reference_value)
                    if value_ref in ("<empty>", None, ""):
                        i += 1
                        continue
                    if value_ref not in appl_alarm_ref_dict:
                        appl_alarm_ref_dict[value_ref] = reference_value
                        i += 1
                    else:
                        # 保证os中alarm引用的唯一性
                        del reference_values[i]
        return task_event_ref_dict, appl_alarm_ref_dict

    @classmethod
    def get_os_sys_appl_set(cls, os_autosar):
        # 有auto_start类型task绑定的app被认为是系统app
        sys_appl_set = set()
        os_tasks = cls.get_os_task_dict(os_autosar, None, False)
        for task in os_tasks.values():
            appl_name = task.get("OsApplName")
            if not appl_name or appl_name == "<OsApp unassigned>":
                continue
            if str(task.get("OsTaskAutostart")) == "TRUE":
                sys_appl_set.add(appl_name)
        return sys_appl_set

    @classmethod
    def get_os_core_list(cls, ecuc_autosar) -> list:
        """获取EcuC UI中配置的核数

        Args:
            ecuc_autosar (class): os ui配置数据

        Returns:
            _type_: UI配置的核列表
        """
        coreid_list = []
        if not ecuc_autosar:
            return coreid_list
        ecuc_core_cfg = ecuc_autosar.find("/ActiveEcuC/EcuC")
        container_values = ecuc_core_cfg.CONTAINERS.ECUC_CONTAINER_VALUE
        for container_value in container_values:
            if container_value.SUB_CONTAINERS is None:
                continue
            def_tag = get_definition_ref(container_value)
            if def_tag.endswith("EcucHardware"):
                if not container_value.SUB_CONTAINERS:
                    return coreid_list
                for sub_container_value in container_value.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
                    parameter_values = getattr(
                        getattr(sub_container_value, "PARAMETER_VALUES", ""), "ECUC_NUMERICAL_PARAM_VALUE", []
                    )
                    for param_val in parameter_values:
                        def_tag = get_definition_ref(param_val)
                        if def_tag.endswith("EcucCoreId"):
                            core_id = get_value(param_val)
                            coreid_list.append(core_id) if core_id not in coreid_list else None
        return coreid_list

    @classmethod
    def get_no_needed_mapping_task_list(cls, ecuc_autosar):
        """返回os模块中无需mapping的task列表,每个核固定4个此名称的系统任务.

        Args:
            ecuc_autosar (class): os ui配置数据

        Returns:
            _type_: list
        """
        coreid_list = [0]
        default_no_needed_mapping_task_list = [
            "Os_System_Timer_Core0",
            "Os_System_Idle_Core0",
            "Os_System_Shell_Core0",
            "Os_System_PreStart_Core0",
        ]
        no_needed_mapping_task_list = default_no_needed_mapping_task_list
        coreid_list = cls.get_os_core_list(ecuc_autosar)
        no_needed_mapping_task_list = (
            [f"Os_System_Timer_Core{item}" for item in coreid_list]
            + [f"Os_System_Idle_Core{item}" for item in coreid_list]
            + [f"Os_System_Shell_Core{item}" for item in coreid_list]
            + [f"Os_System_PreStart_Core{item}" for item in coreid_list]
            if len(coreid_list) >= 1
            else default_no_needed_mapping_task_list
        )
        return no_needed_mapping_task_list

    @classmethod
    def get_sorted_tasks(cls, os_autosar, ecuc_autosar):
        """获取autostart为false的排序后的task信息列表，可作为table的headers使用

        Args:
            os_autosar (_type_): os的autosar数据

        Returns:
            _type_: task综合信息列表
        """
        os_tasks = cls.get_os_task_dict(os_autosar, ecuc_autosar)
        no_needed_mapping_task_list = cls.get_no_needed_mapping_task_list(ecuc_autosar)

        os_sub_tasks = [
            x
            for x in os_tasks.values()
            if x["OsTaskAutostart"] == "FALSE"
            and x["OsTaskType"] in ["BASIC", "EXTENDED"]
            and x["OsTaskName"] not in no_needed_mapping_task_list
        ]
        os_sub_tasks.sort(
            key=lambda x: (
                x.get("CoreId", "0"),
                len(x["OsApplName"]),
                x["OsApplName"].lower(),
                len(x["OsTaskName"]),
                x["OsTaskName"].lower(),
            )
        )
        if len(os_sub_tasks) == 0:
            logger.warning("No available Task.")
        return os_sub_tasks

    @classmethod
    def add_os_schedule_table(cls, os_autosar, mod_autosar, schedule_table_cfg, task_info):
        if schedule_table_cfg is None:
            return

        schedule_table_name = schedule_table_cfg["name"]
        if not schedule_table_name:
            return

        os_container = os_autosar.find("/ActiveEcuC/Os")
        os_schedule_table_container = os_autosar.find(f"/ActiveEcuC/Os/{schedule_table_name}")

        # 2) 创建新的container
        if os_schedule_table_container is None:
            os_schedule_table_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable")
            os_schedule_table_container = AutosarUtil.create_container_value(
                schedule_table_name, os_schedule_table_def, os_container
            )
            AutosarUtil.add_annotation_value(os_schedule_table_container, "IsAutomatic")

        # 3）更新添加os_schedule_table_container.OsSchTblAccessingApplication选项
        appl_set = set()
        appl_set.add(task_info["OsApplName"])
        sys_appl_set = cls.get_os_sys_appl_set(os_autosar)
        appl_set.update(sys_appl_set)
        appl_list = sorted(appl_set, key=lambda x: (len(x), x.lower()))
        appl_ref_set = set()
        os_app_counter_ref = cls.get_os_counter_ref(os_autosar, task_info["CoreId"])
        ref_values = os_schedule_table_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in ref_values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith("OsScheduleTableCounterRef"):
                set_value_ref(value, f"{os_app_counter_ref}")
                pass
            elif def_ref.endswith("OsSchTblAccessingApplication"):
                accessing_application = get_value_ref(value)
                if accessing_application is None:
                    set_value_ref(value, f"/ActiveEcuC/Os/{appl_list[0]}")
                    accessing_application = get_value_ref(value)
                appl_ref_set.add(accessing_application)
        for appl_name in appl_list:
            if appl_name is None:
                continue
            appl_name_ref = f"/ActiveEcuC/Os/{appl_name}"
            if appl_name_ref in appl_ref_set:
                continue
            ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsSchTblAccessingApplication")
            obj = AutosarUtil.set_reference(os_schedule_table_container.REFERENCE_VALUES, ref_def)
            set_value_ref(obj, appl_name_ref)

        counter_info = cls.get_counter_info(os_autosar, os_app_counter_ref)
        param_values = os_schedule_table_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
        param_values += os_schedule_table_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
        for value in param_values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith("OsScheduleTableRepeating"):
                if schedule_table_cfg["repeat"]:
                    set_value(value, "true")
                else:
                    set_value(value, "false")
            elif def_ref.endswith("OsScheduleTableDuration"):
                duration_tick = cls.get_counter_tick(counter_info, schedule_table_cfg["duration"])
                set_value(value, str(duration_tick))
            pass

        # 4）根据expiry point列表去创建sub container
        for index, expiry_point in enumerate(schedule_table_cfg["expiry_point_dict"].keys()):
            os_expiry_point_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsScheduleTableExpiryPoint")
            os_expiry_point_container = AutosarUtil.create_sub_container_value(
                f"ExpiryPoint_{index}", os_expiry_point_def, os_schedule_table_container
            )
            AutosarUtil.add_annotation_value(os_expiry_point_container, "IsAutomatic")
            # 设置一下expiry point的值
            expiry_point_values = os_expiry_point_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
            expiry_point_values += os_expiry_point_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
            for value in expiry_point_values:
                def_ref = get_definition_ref(value)
                if def_ref.endswith("OsScheduleTblExpPointOffset"):
                    expiry_point_tick = cls.get_counter_tick(counter_info, expiry_point)
                    set_value(value, str(expiry_point_tick))
                pass

            activate_task_def = mod_autosar.find(
                "/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsScheduleTableExpiryPoint/OsScheduleTableTaskActivation"
            )
            activate_task_container = AutosarUtil.create_sub_container_value(
                "OsScheduleTableTaskActivation", activate_task_def, os_expiry_point_container
            )
            AutosarUtil.add_annotation_value(activate_task_container, "IsAutomatic")
            # 设置一下ActivateTaskRef的值
            task_name = task_info["OsTaskName"]
            activate_task_ref_values = activate_task_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
            for value in activate_task_ref_values:
                def_ref = get_definition_ref(value)
                if def_ref.endswith("OsScheduleTableActivateTaskRef"):
                    set_value_ref(value, f"/ActiveEcuC/Os/{task_name}")

        pass

    @classmethod
    def remove_os_schedule_table(cls, os_autosar, schedule_table_name):
        os_schedule_table_container = os_autosar.find(f"/ActiveEcuC/Os/{schedule_table_name}")
        if os_schedule_table_container is None:
            return

        # NOTE:倒序遍历删除可以避免list长度变化出现的删除失败问题
        for i in range(len(os_schedule_table_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE) - 1, -1, -1):
            os_expiry_point_container = os_schedule_table_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE[i]
            if not AutosarUtil.is_automatic(os_expiry_point_container):
                continue
            for j in range(len(os_expiry_point_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE) - 1, -1, -1):
                sub_container = os_expiry_point_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE[j]
                parent = sub_container.get_parent()
                AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, sub_container)
            parent = os_expiry_point_container.get_parent()
            AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, os_expiry_point_container)

        parent = os_schedule_table_container.get_parent()
        AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, os_schedule_table_container)
        pass

    @classmethod
    def get_appl_schedule_table_ref_dict(cls, os_autosar, os_appl_name):
        os_app_schedule_table_ref_dict = {}
        if os_appl_name is None:
            return os_app_schedule_table_ref_dict

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return os_app_schedule_table_ref_dict

        values = os_appl_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if not def_ref.endswith("OsAppScheduleTableRef"):
                continue

            value_ref = get_value_ref(value)
            if value_ref not in os_app_schedule_table_ref_dict.keys():
                os_app_schedule_table_ref_dict.update({value_ref: value})
            else:
                values.remove(value)
        return os_app_schedule_table_ref_dict

    @classmethod
    def add_appl_schedule_table_ref(cls, os_autosar, mod_autosar, schedule_table_name, os_appl_name):
        if os_appl_name is None or schedule_table_name is None:
            return

        os_app_schedule_table_ref_dict = cls.get_appl_schedule_table_ref_dict(os_autosar, os_appl_name)
        os_app_schedule_table_ref = f"/ActiveEcuC/Os/{schedule_table_name}"
        if os_app_schedule_table_ref in os_app_schedule_table_ref_dict.keys():
            return

        schedule_table_ref_list = list(os_app_schedule_table_ref_dict.keys())
        if len(schedule_table_ref_list) == 1 and schedule_table_ref_list[0] in ("<empty>", None, ""):
            ref_container = os_app_schedule_table_ref_dict[schedule_table_ref_list[0]]
            set_value_ref(ref_container, os_app_schedule_table_ref)
            return

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return
        os_appl_schedule_table_ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsApplication/OsAppScheduleTableRef")
        obj = AutosarUtil.set_reference(os_appl_container.REFERENCE_VALUES, os_appl_schedule_table_ref_def)
        set_value_ref(obj, os_app_schedule_table_ref)

    @classmethod
    def remove_appl_schedule_table_ref(cls, os_autosar, schedule_table_name, os_appl_name):
        if os_appl_name is None or schedule_table_name is None:
            return

        os_app_schedule_table_ref_dict = cls.get_appl_schedule_table_ref_dict(os_autosar, os_appl_name)
        os_app_schedule_table_ref = f"/ActiveEcuC/Os/{schedule_table_name}"
        if os_app_schedule_table_ref not in os_app_schedule_table_ref_dict.keys():
            return

        schedule_table_ref_list = list(os_app_schedule_table_ref_dict.keys())
        ref_container = os_app_schedule_table_ref_dict[os_app_schedule_table_ref]
        if len(schedule_table_ref_list) == 1 and schedule_table_ref_list[0] == os_app_schedule_table_ref:
            set_value_ref(ref_container, None)
            return

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return
        values = os_appl_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        values.remove(ref_container)
        pass

    @classmethod
    def add_os_alarm_info(cls, os_autosar, mod_autosar, os_alarm_name, os_event_name, task_info):
        if os_alarm_name is None or task_info is None:
            return

        os_container = os_autosar.find("/ActiveEcuC/Os")
        os_alarm_container = os_autosar.find(f"/ActiveEcuC/Os/{os_alarm_name}")
        os_alarm_sub_container = os_autosar.find(f"/ActiveEcuC/Os/{os_alarm_name}/OsAlarmAction")
        # 1) 判断os_alarm_container是否存在，不存在则自动创建
        if os_alarm_container is None:
            os_alarm_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsAlarm")
            os_alarm_action_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsAlarm/OsAlarmAction")
            os_alarm_container = AutosarUtil.create_container_value(os_alarm_name, os_alarm_def, os_container)
            os_alarm_sub_container = AutosarUtil.create_sub_container_value(
                "OsAlarmAction", os_alarm_action_def, os_alarm_container
            )
            AutosarUtil.add_annotation_value(os_alarm_sub_container, "IsAutomatic")
            AutosarUtil.add_annotation_value(os_alarm_container, "IsAutomatic")

        # 2）添加或更新os_alarm_container.OsAlarmAccessingApplication选项
        appl_set = cls.get_os_sys_appl_set(os_autosar)
        if task_info["OsApplName"] != "<OsApp unassigned>":
            appl_set.add(task_info["OsApplName"])
        appl_list = sorted(appl_set, key=lambda x: (len(x), x.lower()))
        appl_ref_dict = {}
        values: list = os_alarm_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith("OsAlarmCounterRef"):
                if "CoreId" in task_info:
                    os_app_counter_ref = cls.get_os_counter_ref(os_autosar, task_info["CoreId"])
                    set_value_ref(value, f"{os_app_counter_ref}")
                pass
            elif def_ref.endswith("OsAlarmAccessingApplication"):
                os_alarm_accessing_application = get_value_ref(value)
                if os_alarm_accessing_application is None:
                    set_value_ref(value, f"/ActiveEcuC/Os/{appl_list[0]}")
                    os_alarm_accessing_application = get_value_ref(value)
                appl_ref_dict[os_alarm_accessing_application] = value
        for appl_name in appl_list:
            if appl_name is None:
                continue
            appl_name_ref = f"/ActiveEcuC/Os/{appl_name}"
            if appl_name_ref in appl_ref_dict:
                appl_ref_dict.pop(appl_name_ref)
                continue
            ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsAlarm/OsAlarmAccessingApplication")
            obj = AutosarUtil.set_reference(os_alarm_container.REFERENCE_VALUES, ref_def)
            set_value_ref(obj, appl_name_ref)

        for value in appl_ref_dict.values():
            values.remove(value)

        # 3）添加或更新os_alarm_sub_choice内选项
        os_task_type = task_info["OsTaskType"]
        alarm_action_cfg_ref = f"/ActiveEcuC/Os/{os_alarm_name}/OsAlarmAction"
        os_alarm_sub_choice_activate = os_autosar.find(f"{alarm_action_cfg_ref}/OsAlarmActivateTask")
        os_alarm_sub_choice_setevent = os_autosar.find(f"{alarm_action_cfg_ref}/OsAlarmSetEvent")
        os_alarm_sub_choice = os_alarm_sub_choice_activate or os_alarm_sub_choice_setevent
        alarm_action_def_ref = "/AUTOSAR/EcucDefs/Os/OsAlarm/OsAlarmAction"
        container_value = getattr(getattr(os_alarm_sub_container, "SUB_CONTAINERS", None), "ECUC_CONTAINER_VALUE", [])
        if os_task_type == "BASIC":
            if os_alarm_sub_choice_setevent:
                AutosarUtil.remove_container_value(container_value, os_alarm_sub_choice_setevent)
            if os_alarm_sub_choice_activate is None:
                activate_task_def = mod_autosar.find(f"{alarm_action_def_ref}/OsAlarmActivateTask")
                os_alarm_sub_choice = AutosarUtil.create_sub_container_choice(
                    "OsAlarmActivateTask", activate_task_def, os_alarm_sub_container
                )
                AutosarUtil.add_annotation_value(os_alarm_sub_choice, "IsAutomatic")
        elif os_task_type == "EXTENDED":
            if os_alarm_sub_choice_activate:
                AutosarUtil.remove_container_value(container_value, os_alarm_sub_choice_activate)
            if os_alarm_sub_choice_setevent is None:
                set_event_def = mod_autosar.find(f"{alarm_action_def_ref}/OsAlarmSetEvent")
                os_alarm_sub_choice = AutosarUtil.create_sub_container_choice(
                    "OsAlarmSetEvent", set_event_def, os_alarm_sub_container
                )
                AutosarUtil.add_annotation_value(os_alarm_sub_choice, "IsAutomatic")
        else:
            logger.warning(f"Unsupported OsTaskType: {os_task_type}")
            return
        task_name = task_info["OsTaskName"]
        values = os_alarm_sub_choice.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith("OsAlarmActivateTaskRef") or def_ref.endswith("OsAlarmSetEventTaskRef"):
                set_value_ref(value, f"/ActiveEcuC/Os/{task_name}")
            elif def_ref.endswith("OsAlarmSetEventRef"):
                if not os_event_name:
                    continue
                set_value_ref(value, f"/ActiveEcuC/Os/{os_event_name}")

    @classmethod
    def get_os_counter_ref(cls, os_autosar, core_id):
        os_app_counter_ref = None
        if not core_id:
            return os_app_counter_ref
        # NOTE: OS组确认system application的名称格式固定
        system_application_name = "SystemApplication_Core" + core_id
        system_application_container = os_autosar.find(f"/ActiveEcuC/Os/{system_application_name}")
        if not system_application_container:
            return os_app_counter_ref

        for reference_value in system_application_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
            def_ref = get_definition_ref(reference_value)
            if not def_ref.endswith("OsAppCounterRef"):
                continue
            # NOTE: OS组确认system application的counter一般只有一个，这里选第一个有效的即可
            os_app_counter_ref = get_value_ref(reference_value)
            if os_app_counter_ref not in (None, "", "<empty>"):
                break

        return os_app_counter_ref

    @classmethod
    def get_counter_info(cls, os_autosar, os_counter_ref):
        counter_info = {}
        if not os_counter_ref:
            return counter_info
        counter_container = os_autosar.find(f"{os_counter_ref}")
        if not counter_container:
            return counter_info
        counter_name = get_short_name(counter_container)
        counter_info.update({"name": counter_name})
        parameter_values = ScheduleTableManager.get_numerical_param_values(counter_container)
        for parameter_value in parameter_values:
            def_ref = get_definition_ref(parameter_value)
            if not def_ref.endswith("OsSecondsPerTick"):
                continue
            value = get_value(parameter_value)
            if value not in (None, "", "<empty>"):
                counter_info.update({"OsSecondsPerTick": value})
                break
        if "OsSecondsPerTick" not in counter_info:
            logger.ui_error(f"the counter {counter_name} is without OsSecondsPerTick value!")

        counter_info["path"] = os_counter_ref
        return counter_info

    @classmethod
    def get_counter_tick(cls, counter_info, time_value):
        seconds_per_tick = counter_info["OsSecondsPerTick"]
        tick_count = ScheduleTableManager.convert_milliseconds_to_tick(seconds_per_tick, time_value)
        return tick_count

    @classmethod
    def remove_os_alarm_info(cls, os_autosar, os_alarm_name):
        alarm_action_cfg_ref = f"/ActiveEcuC/Os/{os_alarm_name}/OsAlarmAction"
        os_alarm_sub_choice = os_autosar.find(f"{alarm_action_cfg_ref}/OsAlarmActivateTask")
        os_alarm_sub_choice = os_alarm_sub_choice or os_autosar.find(f"{alarm_action_cfg_ref}/OsAlarmSetEvent")
        if os_alarm_sub_choice:
            alarm_sub_choice_parent = os_alarm_sub_choice.get_parent()
            AutosarUtil.remove_container_value(alarm_sub_choice_parent.ECUC_CONTAINER_VALUE, os_alarm_sub_choice)

        alarm_action_container = os_autosar.find(f"/ActiveEcuC/Os/{os_alarm_name}/OsAlarmAction")
        if alarm_action_container:
            action_container_parent = alarm_action_container.get_parent()
            AutosarUtil.remove_container_value(action_container_parent.ECUC_CONTAINER_VALUE, alarm_action_container)

        alarm_container = os_autosar.find(f"/ActiveEcuC/Os/{os_alarm_name}")
        if alarm_container:
            alarm_container_parent = alarm_container.get_parent()
            AutosarUtil.remove_container_value(alarm_container_parent.ECUC_CONTAINER_VALUE, alarm_container)
        pass

    @classmethod
    def get_appl_alarm_ref_dict(cls, os_autosar, os_appl_name):
        os_app_alarm_ref_dict = {}
        if os_appl_name is None:
            return os_app_alarm_ref_dict

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return os_app_alarm_ref_dict

        values = os_appl_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if not def_ref.endswith("OsAppAlarmRef"):
                continue

            value_ref = get_value_ref(value)
            if value_ref not in os_app_alarm_ref_dict.keys():
                os_app_alarm_ref_dict.update({value_ref: value})
            else:
                values.remove(value)
        return os_app_alarm_ref_dict

    @classmethod
    def add_appl_alarm_ref(cls, os_autosar, mod_autosar, os_alarm_name, os_appl_name):
        if os_appl_name is None or os_alarm_name is None:
            return

        os_app_alarm_ref_dict = cls.get_appl_alarm_ref_dict(os_autosar, os_appl_name)
        os_app_alarm_ref = f"/ActiveEcuC/Os/{os_alarm_name}"
        if os_app_alarm_ref in os_app_alarm_ref_dict.keys():
            return

        alarm_ref_list = list(os_app_alarm_ref_dict.keys())
        if len(alarm_ref_list) == 1 and alarm_ref_list[0] in ("<empty>", None, ""):
            ref_container = os_app_alarm_ref_dict[alarm_ref_list[0]]
            set_value_ref(ref_container, os_app_alarm_ref)
            return

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return
        os_appl_alarm_ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsApplication/OsAppAlarmRef")
        obj = AutosarUtil.set_reference(os_appl_container.REFERENCE_VALUES, os_appl_alarm_ref_def)
        set_value_ref(obj, os_app_alarm_ref)

    @classmethod
    def remove_appl_alarm_ref(cls, os_autosar, os_alarm_name, os_appl_name):
        if os_appl_name is None or os_alarm_name is None:
            return

        os_app_alarm_ref_dict = cls.get_appl_alarm_ref_dict(os_autosar, os_appl_name)
        os_app_alarm_ref = f"/ActiveEcuC/Os/{os_alarm_name}"
        if os_app_alarm_ref not in os_app_alarm_ref_dict.keys():
            return

        alarm_ref_list = list(os_app_alarm_ref_dict.keys())
        ref_container = os_app_alarm_ref_dict[os_app_alarm_ref]
        if len(alarm_ref_list) == 1 and alarm_ref_list[0] == os_app_alarm_ref:
            set_value_ref(ref_container, None)
            return

        os_appl_container = os_autosar.find(f"/ActiveEcuC/Os/{os_appl_name}")
        if not os_appl_container:
            return
        values = os_appl_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        values.remove(ref_container)
        pass

    @classmethod
    def add_os_event_info(cls, os_autosar, mod_autosar, os_event_name, task_info):
        if os_event_name is None or task_info is None:
            return
        os_task_type = task_info["OsTaskType"]
        if os_task_type == "BASIC":
            return

        os_container = os_autosar.find("/ActiveEcuC/Os")
        os_event_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsEvent")
        os_event_container = os_autosar.find(f"/ActiveEcuC/Os/{os_event_name}")
        if os_event_container is None:
            os_event_container = AutosarUtil.create_container_value(os_event_name, os_event_def, os_container)
            AutosarUtil.add_annotation_value(os_event_container, "IsAutomatic")

        val = None
        evt_name_upper = os_event_name.upper()
        if evt_name_upper == f"Rte_Ev_Timeout_{task_info['OsTaskName']}".upper():
            val = "0"
        elif evt_name_upper == f"Rte_Ev_WaitPoint_{task_info['OsTaskName']}".upper():
            val = "1"
        if val:
            params = os_event_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
            for param in params:
                def_ref = get_definition_ref(param)
                if def_ref.endswith("OsEventMask"):
                    set_value(param, val)

        pass

    @classmethod
    def remove_os_event_info(cls, os_autosar, os_event_name):
        if not os_event_name:
            return

        event_container = os_autosar.find(f"/ActiveEcuC/Os/{os_event_name}")
        if event_container:
            event_container_parent = event_container.get_parent()
            AutosarUtil.remove_container_value(event_container_parent.ECUC_CONTAINER_VALUE, event_container)
        pass

    @classmethod
    def get_task_event_ref_dict(cls, os_autosar, task_info):
        os_task_event_ref_dict = {}
        if task_info is None:
            return os_task_event_ref_dict

        os_task_type = task_info["OsTaskType"]
        if os_task_type == "BASIC":
            return os_task_event_ref_dict

        os_task_name = task_info["OsTaskName"]
        os_task_container = os_autosar.find(f"/ActiveEcuC/Os/{os_task_name}")
        if not os_task_container:
            return os_task_event_ref_dict
        values = os_task_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if not def_ref.endswith("OsTaskEventRef"):
                continue

            value_ref = get_value_ref(value)
            if value_ref not in os_task_event_ref_dict.keys():
                os_task_event_ref_dict.update({value_ref: value})
            else:
                values.remove(value)
        return os_task_event_ref_dict

    @classmethod
    def add_task_event_ref(cls, os_autosar, mod_autosar, os_event_name, task_info):
        if os_event_name is None or task_info is None:
            return
        os_task_type = task_info["OsTaskType"]
        if os_task_type == "BASIC":
            return

        os_task_event_ref_dict = cls.get_task_event_ref_dict(os_autosar, task_info)
        os_task_event_ref = f"/ActiveEcuC/Os/{os_event_name}"
        if os_task_event_ref in os_task_event_ref_dict.keys():
            return

        event_ref_list = list(os_task_event_ref_dict.keys())
        if len(event_ref_list) == 1 and event_ref_list[0] in ("<empty>", None, ""):
            ref_container = os_task_event_ref_dict[event_ref_list[0]]
            set_value_ref(ref_container, os_task_event_ref)
            return
        os_task_name = task_info["OsTaskName"]
        os_task_container = os_autosar.find(f"/ActiveEcuC/Os/{os_task_name}")
        if not os_task_container:
            return
        os_task_event_ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsTask/OsTaskEventRef")
        obj = AutosarUtil.set_reference(os_task_container.REFERENCE_VALUES, os_task_event_ref_def)
        set_value_ref(obj, os_task_event_ref)
        pass

    @classmethod
    def remove_task_event_ref(cls, os_autosar, os_event_name, task_info):
        if task_info is None or os_event_name is None:
            return

        os_task_event_ref_dict = cls.get_task_event_ref_dict(os_autosar, task_info)
        os_task_event_ref = f"/ActiveEcuC/Os/{os_event_name}"
        if os_task_event_ref not in os_task_event_ref_dict.keys():
            return

        event_ref_list = list(os_task_event_ref_dict.keys())
        ref_container = os_task_event_ref_dict[os_task_event_ref]
        if len(event_ref_list) == 1 and event_ref_list[0] == os_task_event_ref:
            set_value_ref(ref_container, None)
            return
        os_task_name = task_info["OsTaskName"]
        os_task_container = os_autosar.find(f"/ActiveEcuC/Os/{os_task_name}")
        if not os_task_container:
            return
        values = os_task_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        values.remove(ref_container)
        pass

    @classmethod
    def remove_all_ioc_info(cls, os_autosar):
        os_ioc_container = os_autosar.find("/ActiveEcuC/Os/OsIoc")
        if os_ioc_container is None:
            return
        # NOTE:倒序遍历删除可以避免list长度变化出现的删除失败问题
        for i in range(len(os_ioc_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE) - 1, -1, -1):
            container_value = os_ioc_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE[i]
            if not AutosarUtil.is_automatic(container_value):
                continue
            for sub_container in container_value.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
                sub_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE = []
            container_value.SUB_CONTAINERS.ECUC_CONTAINER_VALUE = []

            parent = container_value.get_parent()
            AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, container_value)

            # del os_ioc_container.SUB_CONTAINERS.ECUC_CONTAINER_VALUE[i]

        pass

    @classmethod
    def add_ioc_data_properties(cls, data_properties_def, ioc_cfg, os_ioc_communication):
        for data_property in ioc_cfg["OsIocDataProperties"]:
            data_property_container = AutosarUtil.create_sub_container_value(
                data_property["ShortName"], data_properties_def, os_ioc_communication
            )
            AutosarUtil.add_annotation_value(data_property_container, "IsAutomatic")
            values = []
            values += data_property_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
            values += data_property_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
            values += data_property_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
            for value in values:
                def_ref = get_definition_ref(value)
                if def_ref.endswith("OsIocDataPropertyIndex"):
                    set_value(value, data_property["OsIocDataPropertyIndex"])
                elif def_ref.endswith("OsIocInitValue"):
                    set_value(value, data_property["OsIocInitValue"])
                elif def_ref.endswith("OsIocDataTypeRef"):
                    set_value_ref(value, data_property["OsIocDataTypeRef"])

    @classmethod
    def add_ioc_sender_properties(cls, sender_properties_def, ioc_cfg, os_ioc_communication):
        for sender_property in ioc_cfg["OsIocSenderProperties"]:
            sender_property_container = AutosarUtil.create_sub_container_value(
                sender_property["ShortName"], sender_properties_def, os_ioc_communication
            )
            AutosarUtil.add_annotation_value(sender_property_container, "IsAutomatic")
            values = []
            values += sender_property_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
            values += sender_property_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
            values += sender_property_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
            for value in values:
                def_ref = get_definition_ref(value)
                if def_ref.endswith("OsIocFunctionImplementationKind"):
                    set_value(value, sender_property["OsIocFunctionImplementationKind"])
                elif def_ref.endswith("OsIocSenderId"):
                    set_value(value, sender_property["OsIocSenderId"])
                elif def_ref.endswith("OsIocSendingOsApplicationRef"):
                    set_value_ref(value, sender_property["OsIocSendingOsApplicationRef"])

    @classmethod
    def add_ioc_receiver_properties(cls, receiver_properties_ref, ioc_cfg, os_ioc_communication):
        for receiver_property in ioc_cfg["OsIocReceiverProperties"]:
            receiver_property_container = AutosarUtil.create_sub_container_value(
                receiver_property["ShortName"], receiver_properties_ref, os_ioc_communication
            )
            AutosarUtil.add_annotation_value(receiver_property_container, "IsAutomatic")
            values = []
            values += receiver_property_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
            values += receiver_property_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
            values += receiver_property_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
            for value in values:
                def_ref = get_definition_ref(value)
                if def_ref.endswith("OsIocFunctionImplementationKind"):
                    set_value(value, receiver_property["OsIocFunctionImplementationKind"])
                elif def_ref.endswith("OsIocReceiverPullCB"):
                    set_value(value, receiver_property["OsIocReceiverPullCB"])
                elif def_ref.endswith("OsIocReceivingOsApplicationRef"):
                    set_value_ref(value, receiver_property["OsIocReceivingOsApplicationRef"])

    @classmethod
    def add_ioc_info(cls, os_autosar, mod_autosar, ioc_id, ioc_cfg):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        os_ioc_container = os_autosar.find("/ActiveEcuC/Os/OsIoc")
        if os_ioc_container is None:
            os_ioc_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsIoc")
            os_ioc_container = AutosarUtil.create_container_value("OsIoc", os_ioc_def, os_cfg)

        communication_def_ref = "/AUTOSAR/EcucDefs/Os/OsIoc/OsIocCommunication"
        data_properties_def = mod_autosar.find(f"{communication_def_ref}/OsIocDataProperties")
        sender_properties_def = mod_autosar.find(f"{communication_def_ref}/OsIocSenderProperties")
        receiver_properties_ref = mod_autosar.find(f"{communication_def_ref}/OsIocReceiverProperties")

        os_ioc_communication = os_autosar.find(f"/ActiveEcuC/Os/OsIoc/{ioc_id}")
        if os_ioc_communication is None:
            communication_def = mod_autosar.find(communication_def_ref)
            os_ioc_communication = AutosarUtil.create_sub_container_value(ioc_id, communication_def, os_ioc_container)
            AutosarUtil.add_annotation_value(os_ioc_communication, "IsAutomatic")

        for param_value in os_ioc_communication.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE:
            def_ref = get_definition_ref(param_value)
            if def_ref.endswith("OsIocBufferLength"):
                set_value(param_value, ioc_cfg["OsIocBufferLength"])
        cls.add_ioc_data_properties(data_properties_def, ioc_cfg, os_ioc_communication)
        cls.add_ioc_sender_properties(sender_properties_def, ioc_cfg, os_ioc_communication)
        cls.add_ioc_receiver_properties(receiver_properties_ref, ioc_cfg, os_ioc_communication)

        pass

    @classmethod
    def add_all_rte_schedule_table_info(cls, os_autosar, mod_autosar, all_rte_schedule_table_cfg):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        appl_containers = {
            get_short_name(appl): appl
            for appl in ScheduleTableManager.get_container_values(os_cfg)
            if get_definition_ref(appl).endswith("OsApplication")
        }
        ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsApplication/OsAppScheduleTableRef")
        appl_list = OsManager.get_os_sch_tbl_appl_list(os_autosar)
        for sch_tbl in all_rte_schedule_table_cfg:
            appl_cont = appl_containers.get(sch_tbl["osa"], None)
            if not appl_cont:
                continue

            set_value_ref(AutosarUtil.set_reference(appl_cont.REFERENCE_VALUES, ref_def), f"/ActiveEcuC/Os/{sch_tbl['name']}")
            OsManager.update_os_schedule_table(os_autosar, mod_autosar, sch_tbl, appl_list)


    @classmethod
    def remove_all_rte_schedule_table_info(cls, os_autosar):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        appl_container_list = [
            appl
            for appl in ScheduleTableManager.get_container_values(os_cfg)
            if get_definition_ref(appl).endswith("OsApplication")
        ]
        for i in range(len(os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE) - 1, -1, -1):
            container_value = os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE[i]

            def_ref: str = get_definition_ref(container_value)
            if not def_ref.endswith("OsScheduleTable"):
                continue

            table_name = get_short_name(container_value)
            if not AutosarUtil.is_automatic(container_value) or not table_name.startswith("Rte_St_"):
                continue

            OsManager.remove_os_sch_tbl(os_autosar, table_name)
            OsManager.remove_appl_sch_tbl_ref(appl_container_list, table_name)
        pass


    @classmethod
    def remove_all_spinlock_info(cls, os_autosar):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        for i in range(len(os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE) - 1, -1, -1):
            container_value = os_cfg.CONTAINERS.ECUC_CONTAINER_VALUE[i]

            if not AutosarUtil.is_automatic(container_value):
                continue
            def_ref: str = get_definition_ref(container_value)
            if not def_ref.endswith("OsSpinlock"):
                continue
            parent = container_value.get_parent()
            AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, container_value)
        pass

    @classmethod
    def remove_spinlock_info(cls, os_autosar, spinlock_id):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        os_spinlock = os_cfg.find(f"/ActiveEcuC/Os/{spinlock_id}")
        if os_spinlock:
            parent = os_spinlock.get_parent()
            AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, os_spinlock)

    @classmethod
    def add_spinlock_info(cls, os_autosar, mod_autosar, spinlock_id, appl_name_list, is_automatic=True):
        os_cfg = os_autosar.find("/ActiveEcuC/Os")
        os_spinlock = os_cfg.find(f"/ActiveEcuC/Os/{spinlock_id}")
        os_spinlock_def_ref = "/AUTOSAR/EcucDefs/Os/OsSpinlock"
        spinlock_def = mod_autosar.find(os_spinlock_def_ref)
        if os_spinlock is None:
            os_spinlock = AutosarUtil.create_sub_container_value(spinlock_id, spinlock_def, os_cfg)
            if is_automatic:
                AutosarUtil.add_annotation_value(os_spinlock, "IsAutomatic")

        accessing_application_def = mod_autosar.find(f"{os_spinlock_def_ref}/OsSpinlockAccessingApplication")

        values = []
        values += os_spinlock.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        values += os_spinlock.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith("OsSpinlockAccessingApplication"):
                appl_ref = f"/ActiveEcuC/Os/{appl_name_list[0]}"
                set_value_ref(value, appl_ref)
            elif def_ref.endswith("OsSpinlockLockType"):
                spinlock_locktype = "OPTIMIZED"
                set_value(value, spinlock_locktype)
            elif def_ref.endswith("OsSpinlockLockMethod"):
                spinlock_method = appl_name_list[-1]
                set_value(value, spinlock_method)
        for appl_name in appl_name_list[1:-1]:
            accessing_application = AutosarUtil.set_reference(os_spinlock.REFERENCE_VALUES, accessing_application_def)
            appl_ref = f"/ActiveEcuC/Os/{appl_name}"
            set_value_ref(accessing_application, appl_ref)

        pass

    @classmethod
    def get_os_param_container(cls, os_autosar, active_path, param_name):
        # eg:OsTaskPriority, 后面可以优化成枚举的形式
        value_container = None
        event_container = os_autosar.find(active_path)
        if not event_container:
            return value_container

        values = []
        values += event_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        values += event_container.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
        values += event_container.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
        for value in values:
            def_ref = get_definition_ref(value)
            if def_ref.endswith(f"{param_name}"):
                value_container = value
                break
        return value_container

    @classmethod
    def get_os_param_value(cls, os_autosar, active_path, param_name):
        param_value = None
        value_container = cls.get_os_param_container(os_autosar, active_path, param_name)
        if not value_container:
            return param_value

        tag = value_container.original_tagname_
        if tag in ["ECUC-NUMERICAL-PARAM-VALUE", "ECUC-TEXTUAL-PARAM-VALUE"]:
            param_value = get_value(value_container)
        elif tag in ["ECUC-REFERENCE-VALUE"]:
            param_value = get_value_ref(value_container)

        return param_value

    @classmethod
    def set_os_param_value(cls, os_autosar, active_path, param_name, param_value):
        value_container = cls.get_os_param_container(os_autosar, active_path, param_name)
        if not value_container:
            return

        tag = value_container.original_tagname_
        if tag in ["ECUC-NUMERICAL-PARAM-VALUE", "ECUC-TEXTUAL-PARAM-VALUE"]:
            set_value(value_container, param_value)
        elif tag in ["ECUC-REFERENCE-VALUE"]:
            set_value_ref(value_container, param_value)
        return

    @classmethod
    def get_partition_asil_level(cls, appl_name, partition_ref, ecuc_autosar):
        """
        asil_level: "D / C / B / A / QM" -> "ASIL D / ASIL C / ASIL B / ASIL A / QM"
        """
        asil_level = "QM"
        ecuc_partition = None
        swc_inst_ref = []
        if not partition_ref or not ecuc_autosar:
            return asil_level, ecuc_partition, swc_inst_ref
        partition_ar = ecuc_autosar.find(partition_ref)
        if partition_ar is None:
            logger.error(f"{appl_name} OsAppEcucPartitionRef: {partition_ar} not found!")
            return asil_level, ecuc_partition, swc_inst_ref
        ecuc_partition = get_short_name(partition_ar)
        parameter_values = getattr(getattr(partition_ar, "PARAMETER_VALUES", ""), "ECUC_TEXTUAL_PARAM_VALUE", [])
        for param_val in parameter_values:
            def_tag = get_definition_ref(param_val)
            if def_tag.endswith("ASIL"):
                asil_level = get_value(param_val)
                break
        inst_ref_values = getattr(getattr(partition_ar, "REFERENCE_VALUES", ""), "ECUC_INSTANCE_REFERENCE_VALUE", [])
        for inst_ref_value in inst_ref_values:
            ref_tag = get_definition_ref(inst_ref_value)
            if ref_tag.endswith("EcucPartitionSoftwareComponentInstanceRef"):
                target_ref = getattr(getattr(inst_ref_value, "VALUE_IREF", ""), "TARGET_REF", "")
                if target_ref:
                    swc_instance = target_ref.valueOf_
                    if swc_instance:
                        swc_inst_ref.append(swc_instance.split("/")[-1])
        return asil_level, ecuc_partition, swc_inst_ref

    @classmethod
    def parse_os_autosar(cls, os_autosar, ecuc_autosar):
        if not os_autosar:
            return {}
        os_cfg = {}
        os_cfg["OsTasks"] = {}
        os_cfg["OsApplications"] = {}
        os_cfg["os_counter"] = {}
        os_cfg["asil"] = {}
        os_cfg["os_alarms"] = {}
        os = os_autosar.find("/ActiveEcuC/Os")
        os_core_counter_map = {}
        for container_value in os.CONTAINERS.ECUC_CONTAINER_VALUE:
            name = get_short_name(container_value)
            def_ref = get_definition_ref(container_value)
            if def_ref.endswith("OsTask"):
                if not container_value.PARAMETER_VALUES:
                    continue
                task_info = {}
                task_info["OsTaskAutostart"] = "FALSE"
                os_cfg["OsTasks"][name] = task_info
                parameter_values = []
                parameter_values += container_value.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE
                parameter_values += container_value.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE
                for parameter_value in parameter_values:
                    def_ref = get_definition_ref(parameter_value)
                    if def_ref.endswith("OsTaskPriority"):
                        task_info["OsTaskPriority"] = get_value(parameter_value)
                    elif def_ref.endswith("OsTaskSchedule"):
                        task_info["OsTaskSchedule"] = get_value(parameter_value)
                    elif def_ref.endswith("OsTaskType"):
                        task_info["OsTaskType"] = get_value(parameter_value)

                reference_values = []
                reference_values += container_value.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
                task_info["OsTaskEventRef"] = []
                for reference_value in reference_values:
                    def_ref = get_definition_ref(reference_value)
                    if def_ref.endswith("OsTaskEventRef"):
                        if reference_value.VALUE_REF is not None:
                            task_info["OsTaskEventRef"].append(reference_value.VALUE_REF.valueOf_)

                if not container_value.SUB_CONTAINERS:
                    continue
                for sub_container_value in container_value.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
                    def_tag = get_definition_ref(sub_container_value)
                    if def_tag.endswith("OsTaskAutostart"):
                        task_info["OsTaskAutostart"] = "TRUE"
            elif def_ref.endswith("OsApplication"):
                os_application = {}
                os_application["OsAppTaskRef"] = []
                os_cfg["OsApplications"][name] = os_application
                if container_value.PARAMETER_VALUES:
                    for param_val in container_value.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE:
                        def_ref = get_definition_ref(param_val)
                        if def_ref.endswith("OsIsPrivileged"):
                            os_application["OsIsPrivileged"] = get_value(param_val) == "true"
                if container_value.REFERENCE_VALUES:
                    for reference_value in container_value.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
                        def_ref = get_definition_ref(reference_value)
                        if def_ref.endswith("OsAppTaskRef"):
                            os_app_task_ref = get_value_ref(reference_value) or ""
                            task_name = os_app_task_ref.split("/").pop()
                            os_application["OsAppTaskRef"].append(task_name)
                        elif def_ref.endswith("OsApplicationCoreRef"):
                            core_ref = get_value_ref(reference_value) or ""
                            os_application["CoreId"] = cls.get_core_id(name, core_ref, ecuc_autosar)
                        elif def_ref.endswith("OsAppEcucPartitionRef"):
                            (
                                os_cfg["asil"][name],
                                os_application["EcucPartition"],
                                os_application["EcucPartitionSwcInstRef"],
                            ) = cls.get_partition_asil_level(name, get_value_ref(reference_value), ecuc_autosar)
                        else:
                            pass

                os_app_counter_ref = cls.get_os_counter_ref(os_autosar, os_application["CoreId"])
                counter_info = cls.get_counter_info(os_autosar, os_app_counter_ref)
                if os_application["CoreId"] not in os_core_counter_map:
                    os_core_counter_map[os_application["CoreId"]] = counter_info
                elif counter_info["name"] != os_core_counter_map[os_application["CoreId"]]["name"]:
                    logger.ui_error(f'multiple OsCounters found in core {os_application["CoreId"]}')
                os_application.update({"OsAppCounter": counter_info})
                pass
            else:
                pass
        for osa_name, osa in os_cfg["OsApplications"].items():
            for task_name in osa["OsAppTaskRef"]:
                if not task_name:
                    continue
                os_cfg["OsTasks"][task_name]["osa"] = osa_name
            if "OsAppCounter" not in os_application:
                osa["OsAppCounter"] = os_core_counter_map.get(osa["CoreId"], {})
                if not osa["OsAppCounter"]:
                    logger.ui_error(f'NO OsCounter found in core {osa["CoreId"]}')
        return os_cfg

    @classmethod
    def get_os_sch_tbl_cfgs(cls, os_autosar):
        sch_tbl_cfgs = {}
        if not os_autosar:
            return sch_tbl_cfgs
        os_sch_tbl_list = ScheduleTableManager.get_ecuc_cfg(os_autosar, "/ActiveEcuC/Os", "OsScheduleTable")
        for os_sch_tbl in os_sch_tbl_list:
            os_sch_tbl_dict = {}
            os_sch_tbl_dict["name"] = os_sch_tbl["ShortName"]
            os_sch_tbl_dict["is_automatic"] = os_sch_tbl["IsAutomatic"]
            os_sch_tbl_dict["is_autostart"] = False
            os_sch_tbl_dict["repeating"] = bool(os_sch_tbl["OsScheduleTableRepeating"] == "true")
            os_sch_tbl_dict["duration"] = int(os_sch_tbl["OsScheduleTableDuration"] or 0)
            os_sch_tbl_dict["counter_ref"] = os_sch_tbl["OsScheduleTableCounterRef"]
            os_sch_tbl_dict["counter_info"] = cls.get_counter_info(os_autosar, os_sch_tbl["OsScheduleTableCounterRef"])
            expiry_points = {}
            for expiry_point in os_sch_tbl["SubContainers"]:
                if expiry_point["DefName"] == "OsScheduleTableAutostart":
                    os_sch_tbl_dict["is_autostart"] = True
                    continue
                if expiry_point["DefName"] != "OsScheduleTableExpiryPoint":
                    continue
                if not expiry_point["OsScheduleTblExpPointOffset"]:
                    break
                offset = int(expiry_point["OsScheduleTblExpPointOffset"])
                for action in expiry_point["SubContainers"]:
                    def_name = action["DefName"]
                    if def_name == "OsScheduleTableTaskActivation":
                        event_name = ""
                        task_name = ScheduleTableManager.get_basename(action["OsScheduleTableActivateTaskRef"])
                    elif def_name.endswith("OsScheduleTableEventSetting"):
                        event_name = ScheduleTableManager.get_basename(action["OsScheduleTableSetEventRef"])
                        task_name = ScheduleTableManager.get_basename(action["OsScheduleTableSetEventTaskRef"])
                    expiry_points.setdefault(offset, []).append(
                        {
                            "offset": offset,
                            "task_name": task_name,
                            "event_name": event_name,
                        }
                    )
            os_sch_tbl_dict["expiry_points"] = expiry_points
            sch_tbl_cfgs[os_sch_tbl_dict["name"]] = os_sch_tbl_dict
        return sch_tbl_cfgs

    @classmethod
    def get_os_sch_tbl_container(cls, os_autosar, mod_autosar, sch_tbl_cfg):
        schedule_table_name = sch_tbl_cfg["name"]
        os_container = os_autosar.find("/ActiveEcuC/Os")
        sch_tbl_container = os_autosar.find(f"/ActiveEcuC/Os/{schedule_table_name}")
        if (
            "expiry_point_dict" in sch_tbl_cfg
            and sch_tbl_cfg.get("repeating", True) is False
            and sch_tbl_container is None
        ):
            os_schedule_table_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable")
            sch_tbl_container = AutosarUtil.create_container_value(
                schedule_table_name, os_schedule_table_def, os_container
            )
            AutosarUtil.add_annotation_value(sch_tbl_container, "IsAutomatic")
        return sch_tbl_container

    @classmethod
    def get_os_sch_tbl_appl_list(cls, os_autosar):
        sys_appl_set = cls.get_os_sys_appl_set(os_autosar)
        appl_list = sorted(sys_appl_set, key=lambda x: (len(x), x))
        return appl_list

    @classmethod
    def create_os_sch_tbl_exp_point_container(cls, sch_tbl_container, mod_autosar, index):
        expiry_point_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsScheduleTableExpiryPoint")
        expiry_point_container = AutosarUtil.create_sub_container_value(
            "ExpiryPoint", expiry_point_def, sch_tbl_container, f"ExpiryPoint_{index}"
        )
        AutosarUtil.add_annotation_value(expiry_point_container, "IsAutomatic")
        return expiry_point_container

    @classmethod
    def update_appl_init_sch_tbl_ref(cls, mod_autosar, appl_container_list, init_sch_tbl_cfg, main_sch_tbl_cfg):
        if not init_sch_tbl_cfg.get("expiry_point_dict"):
            return
        init_sch_tbl_name = init_sch_tbl_cfg.get("name", "")
        main_sch_tbl_name = main_sch_tbl_cfg.get("name", "")
        init_sch_tbl_ref = f"/ActiveEcuC/Os/{init_sch_tbl_name}"
        main_sch_tbl_ref = f"/ActiveEcuC/Os/{main_sch_tbl_name}"
        main_appl_container = None
        sch_tbl_ref_set = set()
        for appl_container in appl_container_list:
            ref_values = ScheduleTableManager.get_reference_values(appl_container)
            for ref_value in ref_values:
                def_ref = ScheduleTableManager.get_definition_ref(ref_value)
                if not def_ref.endswith("OsAppScheduleTableRef"):
                    continue
                sch_tbl_ref = get_value_ref(ref_value)
                if sch_tbl_ref == main_sch_tbl_ref:
                    main_appl_container = appl_container
                if sch_tbl_ref:
                    sch_tbl_ref_set.add(sch_tbl_ref)
            if main_appl_container:
                break
        if main_appl_container and init_sch_tbl_ref not in sch_tbl_ref_set:
            ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsApplication/OsAppScheduleTableRef")
            obj = AutosarUtil.set_reference(main_appl_container.REFERENCE_VALUES, ref_def)
            set_value_ref(obj, init_sch_tbl_ref)

    @classmethod
    def add_os_sch_tbl_accessing_appl(cls, os_schedule_table_container, mod_autosar, appl_list):
        appl_ref_set = set()
        ref_values = ScheduleTableManager.get_reference_values(os_schedule_table_container)
        for value in ref_values:
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if def_ref.endswith("OsSchTblAccessingApplication"):
                accessing_application = get_value_ref(value)
                if accessing_application is None:
                    set_value_ref(value, f"/ActiveEcuC/Os/{appl_list[0]}")
                    accessing_application = get_value_ref(value)
                appl_ref_set.add(accessing_application)
        for appl_name in appl_list:
            if appl_name is None:
                continue
            appl_name_ref = f"/ActiveEcuC/Os/{appl_name}"
            if appl_name_ref in appl_ref_set:
                continue
            ref_def = mod_autosar.find("/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsSchTblAccessingApplication")
            obj = AutosarUtil.set_reference(os_schedule_table_container.REFERENCE_VALUES, ref_def)
            set_value_ref(obj, appl_name_ref)

    @classmethod
    def add_os_sch_tbl_expiry_point(cls, sch_tbl_container, mod_autosar, sch_tbl_cfg):
        if "expiry_point_dict" not in sch_tbl_cfg:
            return
        i = 0
        for offset, expiry_points in sch_tbl_cfg["expiry_point_dict"].items():
            expiry_point_container = cls.create_os_sch_tbl_exp_point_container(sch_tbl_container, mod_autosar, i)
            cls.update_os_sch_tbl_exp_point_offset(expiry_point_container, offset)
            i += 1
            event_setting_i = 0
            task_activation_i = 0
            add_action_set = set()
            for _, expiry_point in expiry_points:
                task_name = expiry_point["task_name"]
                event_name = expiry_point["event_name"]
                action_id = task_name + event_name
                if action_id in add_action_set:
                    continue
                add_action_set.add(action_id)
                if event_name:
                    cls.add_os_sch_tbl_event_setting(
                        expiry_point_container, mod_autosar, task_name, event_name, event_setting_i
                    )
                    event_setting_i += 1
                else:
                    cls.add_os_sch_tbl_task_activation(
                        expiry_point_container, mod_autosar, task_name, task_activation_i
                    )
                    task_activation_i += 1

    @classmethod
    def add_os_sch_tbl_task_activation(cls, expiry_point_container, mod_autosar, task_name, index):
        activate_task_def = mod_autosar.find(
            "/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsScheduleTableExpiryPoint/OsScheduleTableTaskActivation"
        )
        activate_task_container = AutosarUtil.create_sub_container_value(
            "", activate_task_def, expiry_point_container, f"OsScheduleTableTaskActivation_{index:03}"
        )
        AutosarUtil.add_annotation_value(activate_task_container, "IsAutomatic")
        activate_task_ref_values = activate_task_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in activate_task_ref_values:
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if not def_ref.endswith("OsScheduleTableActivateTaskRef"):
                continue
            set_value_ref(value, f"/ActiveEcuC/Os/{task_name}")

    @classmethod
    def add_os_sch_tbl_event_setting(cls, expiry_point_container, mod_autosar, task_name, event_name, index):
        event_setting_def = mod_autosar.find(
            "/AUTOSAR/EcucDefs/Os/OsScheduleTable/OsScheduleTableExpiryPoint/OsScheduleTableEventSetting"
        )
        event_setting_container = AutosarUtil.create_sub_container_value(
            "", event_setting_def, expiry_point_container, f"OsScheduleTableEventSetting_{index:03}"
        )
        AutosarUtil.add_annotation_value(event_setting_container, "IsAutomatic")
        event_setting_ref_values = event_setting_container.REFERENCE_VALUES.ECUC_REFERENCE_VALUE
        for value in event_setting_ref_values:
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if def_ref.endswith("OsScheduleTableSetEventRef"):
                set_value_ref(value, f"/ActiveEcuC/Os/{event_name}")
            elif def_ref.endswith("OsScheduleTableSetEventTaskRef"):
                set_value_ref(value, f"/ActiveEcuC/Os/{task_name}")

    @classmethod
    def update_os_schedule_table(cls, os_autosar, mod_autosar, sch_tbl_cfg, appl_list):
        if not sch_tbl_cfg or not sch_tbl_cfg.get("name"):
            return False
        sch_tbl_container = cls.get_os_sch_tbl_container(os_autosar, mod_autosar, sch_tbl_cfg)
        if not sch_tbl_container:
            return False
        if not sch_tbl_cfg.get("expiry_point_dict") and not sch_tbl_cfg.get("repeating", True):
            container_values = ScheduleTableManager.get_container_values(sch_tbl_container.get_parent())
            AutosarUtil.remove_container_value(container_values, sch_tbl_container)
            return True
        cls.update_os_sch_tbl_duration_and_repeating(sch_tbl_container, sch_tbl_cfg)
        cls.update_os_sch_tbl_counter_ref(sch_tbl_container, sch_tbl_cfg)
        cls.update_os_sch_tbl_accessing_appl(sch_tbl_container, mod_autosar, appl_list)
        cls.update_os_sch_tbl_expiry_point(sch_tbl_container, mod_autosar, sch_tbl_cfg)
        return True

    @classmethod
    def update_os_sch_tbl_counter_ref(cls, sch_tbl_container, sch_tbl_cfg):
        if sch_tbl_cfg.get("repeating", True) or not sch_tbl_cfg.get("counter_ref"):
            return
        for ref_values in ScheduleTableManager.get_reference_values(sch_tbl_container):
            def_ref = ScheduleTableManager.get_definition_ref(ref_values)
            if not def_ref.endswith("OsScheduleTableCounterRef"):
                continue
            set_value_ref(ref_values, sch_tbl_cfg["counter_ref"])

    @classmethod
    def update_os_sch_tbl_expiry_point(cls, sch_tbl_container, mod_autosar, sch_tbl_cfg):
        cls.remove_os_sch_tbl_expiry_point(sch_tbl_container)
        cls.add_os_sch_tbl_expiry_point(sch_tbl_container, mod_autosar, sch_tbl_cfg)

    @classmethod
    def update_os_sch_tbl_accessing_appl(cls, sch_tbl_container, mod_autosar, appl_list):
        cls.remove_os_sch_tbl_accessing_appl(sch_tbl_container)
        cls.add_os_sch_tbl_accessing_appl(sch_tbl_container, mod_autosar, appl_list)

    @classmethod
    def update_os_sch_tbl_exp_point_offset(cls, expiry_point_container, offset):
        expiry_point_values = ScheduleTableManager.get_numerical_param_values(expiry_point_container)
        for value in expiry_point_values:
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if not def_ref.endswith("OsScheduleTblExpPointOffset"):
                continue
            set_value(value, str(offset))

    @classmethod
    def update_os_sch_tbl_duration_and_repeating(cls, sch_tbl_container, sch_tbl_cfg):
        param_values = ScheduleTableManager.get_numerical_param_values(sch_tbl_container)
        for value in param_values:
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if def_ref.endswith("OsScheduleTableDuration"):
                set_value(value, str(sch_tbl_cfg.get("duration", "")))
            elif def_ref.endswith("OsScheduleTableRepeating"):
                set_value(value, str(sch_tbl_cfg.get("repeating", True)).lower())

    @classmethod
    def remove_os_sch_tbl(cls, os_autosar, schedule_table_name):
        sch_tbl_container = os_autosar.find(f"/ActiveEcuC/Os/{schedule_table_name}")
        if sch_tbl_container is None:
            return False
        expiry_points = ScheduleTableManager.get_container_values(sch_tbl_container)
        for i in range(len(expiry_points) - 1, -1, -1):
            actions = ScheduleTableManager.get_container_values(expiry_points[i])
            for j in range(len(actions) - 1, -1, -1):
                AutosarUtil.remove_container_value(actions, actions[j])
            AutosarUtil.remove_container_value(expiry_points, expiry_points[i])
        parent = sch_tbl_container.get_parent()
        AutosarUtil.remove_container_value(parent.ECUC_CONTAINER_VALUE, sch_tbl_container)
        return True

    @classmethod
    def remove_appl_sch_tbl_ref(cls, appl_container_list, schedule_table_name):
        sch_tbl_ref = f"/ActiveEcuC/Os/{schedule_table_name}"
        for appl_container in appl_container_list:
            ref_values = ScheduleTableManager.get_reference_values(appl_container)
            for ref_value in ref_values:
                def_ref = ScheduleTableManager.get_definition_ref(ref_value)
                if not def_ref.endswith("OsAppScheduleTableRef"):
                    continue
                if get_value_ref(ref_value) == sch_tbl_ref:
                    ref_values.remove(ref_value)
                    return True
        return False

    @classmethod
    def remove_os_sch_tbl_accessing_appl(cls, sch_tbl_container):
        ref_values = ScheduleTableManager.get_reference_values(sch_tbl_container)
        for i in range(len(ref_values) - 1, -1, -1):
            value = ref_values[i]
            def_ref = ScheduleTableManager.get_definition_ref(value)
            if not def_ref.endswith("OsSchTblAccessingApplication"):
                continue
            ref_values.pop(i)

    @classmethod
    def remove_os_sch_tbl_expiry_point(cls, sch_tbl_container):
        expiry_points = ScheduleTableManager.get_container_values(sch_tbl_container)
        expiry_points.clear()
        gc.collect()
