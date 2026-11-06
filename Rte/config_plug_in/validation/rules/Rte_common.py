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
from func_module.validation.common.validation_def import ValidationData
from func_module.generator.rte.rte_parser import get_task_mappings_info, get_rte_codegen_dict
from basic_func_module.autosar_utils.autosar_utils import AutosarUtils
from func_module.mapping.task_mapping_core import TaskMappingInstance
from enum import IntEnum
import re


class RteCommonData:

    def __init__(self, validation_data: ValidationData):
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.system_autosar_dict = validation_data.autosar_system_class
        self.bsw_ecuc_autosar_dict = validation_data.autosar_bsw_class
        self.internal_behavior_autosar_dict = validation_data.autosar_ib_class
        self.autosar_mod_class = validation_data.autosar_mod_class

        self.idts = None
        self.asw_cfg = None
        self.all_ports = None
        self.mapped_ports = None
        self.data_mappings = None
        self.data_mapping_all_ports = None
        self.system_signals = None
        self.task_mapping_instance = None
        self.task_mappings_info = None
        self.sw_component_prototypes = None
        self.ecuc_partition_info = None

    def get_mapped_ports(self):
        return self.mapped_ports

    def get_all_sw_component_prototypes(self):
        if not self.sw_component_prototypes:
            self.sw_component_prototypes = AutosarUtils.get_all_sw_component_prototypes(self.asw_autosar_dict)
        return self.sw_component_prototypes

    def get_ecuc_partition_info(self):
        if not self.ecuc_partition_info:
            self.ecuc_partition_info = AutosarUtils.get_ecuc_partition_info()
        return self.ecuc_partition_info

    def get_task_mappings_info(self):
        if not self.task_mappings_info:
            self.task_mappings_info = get_task_mappings_info(
                self.asw_autosar_dict, self.internal_behavior_autosar_dict, self.bsw_ecuc_autosar_dict
            )
        return self.task_mappings_info

    def get_asw_cfg(self):
        # 此处依赖 rte os ecuc 模块，所以需要判定
        for rely_module in ["Rte", "Os", "EcuC"]:
            if rely_module not in self.bsw_ecuc_autosar_dict.keys():
                return None

        if not self.asw_cfg:
            asw_dict = {"asw": self.asw_autosar_dict, "FlatExtract": self.system_autosar_dict["FlatExtract"]}
            cfg_dict = {"asw": "", "rte": {}, "bsw": {}, "dbc": [], "ldf": [], "cdd": {}, "eb": {}}
            self.asw_cfg, _ = get_rte_codegen_dict(
                asw_dict,
                self.bsw_ecuc_autosar_dict,
                self.system_autosar_dict,
                self.internal_behavior_autosar_dict,
                cfg_dict,
            )
        return self.asw_cfg

    def has_access_point(self, port_a, port_b) -> bool:
        rv = False
        if port_a["Interface_type"] == "CLIENT-SERVER-INTERFACE":
            de_a_list = list(port_a["args"].keys())
            for de in de_a_list:
                if not list(port_a["args"][de].keys()):
                    # operation里没有arg，只是调一下server的服务
                    return True
                arg_1 = list(port_a["args"][de].keys())[0]
                if (
                    port_a["args"][de][arg_1]["map_runnable"] is True
                    and port_b["args"].get(de, {}).get(arg_1, {}).get("map_runnable", {}) is True
                ):
                    return True
        elif port_a["Interface_type"] in ["SENDER-RECEIVER-INTERFACE", "NV-DATA-INTERFACE"]:
            de_a_list = list(port_a["args"].keys())
            for de in de_a_list:
                if (
                    port_a["args"][de]["datatype"]["map_runnable"] is True
                    and port_b["args"].get(de, {}).get("datatype", {}).get("map_runnable", {}) is True
                ):
                    return True
        else:
            return True
        return rv

    def get_task_mapping_instance(self):
        check_ret, _ = TaskMappingInstance.check_task_mapping_config(self.bsw_ecuc_autosar_dict)
        if not check_ret:
            return None
        self.task_mapping_instance = TaskMappingInstance.get_task_mapping_instance()
        if not self.task_mapping_instance:
            self.task_mapping_instance = TaskMappingInstance.update_task_mapping_instance(
                self.asw_autosar_dict,
                self.bsw_ecuc_autosar_dict,
                self.system_autosar_dict,
                self.internal_behavior_autosar_dict,
                self.autosar_mod_class,
            )
        return self.task_mapping_instance

    def get_root_item(self):
        check_ret, _ = TaskMappingInstance.check_task_mapping_config(self.bsw_ecuc_autosar_dict)
        if not check_ret:
            return None
        task_mapping_instance = self.get_task_mapping_instance()
        return task_mapping_instance.root_item

    def get_item_map(self):
        check_ret, _ = TaskMappingInstance.check_task_mapping_config(self.bsw_ecuc_autosar_dict)
        if not check_ret:
            return None
        task_mapping_instance = self.get_task_mapping_instance()
        return task_mapping_instance.item_map

    def get_item_data_by_id(self, id):
        check_ret, _ = TaskMappingInstance.check_task_mapping_config(self.bsw_ecuc_autosar_dict)
        if not check_ret:
            return None
        task_mapping_instance = self.get_task_mapping_instance()
        index = task_mapping_instance.get_item_index(id)

        return task_mapping_instance.get_item_data(index)

    def get_datatype_mapping_sets(self):
        self.datatype_mapping_sets, self.adt_mappings = AutosarUtils.parse_datatype_mapping_sets_for_validation(
            self.asw_autosar_dict
        )
        return self.datatype_mapping_sets, self.adt_mappings


class RteUtils:

    @classmethod
    def get_port_info(cls, port_mapping_item, asw_cfg, idts, port_key):
        # sender/receiver client/server
        is_swc_ok = False
        port_type = None
        category = None
        data_type = None
        data_size = None
        struct_member_list = []
        if port_key == "provider_iref":
            port_swc = port_mapping_item[port_key]["target_pport_ref"].split("/")[-2]
        else:
            port_swc = port_mapping_item[port_key]["target_rport_ref"].split("/")[-2]
        if port_swc not in asw_cfg:
            # logger.warning(f"{port_swc} not in asw_cfg!")
            return is_swc_ok, port_type, category, data_type, data_size, struct_member_list

        is_swc_ok = True
        port_ref_key = "target_pport_ref" if port_key == "provider_iref" else "target_rport_ref"
        port_ref = port_mapping_item[port_key][port_ref_key]
        swc_port_key = "pports" if port_key == "provider_iref" else "rports"
        # 如果是server，那就匹配名称; 如果是client，那就匹配path; 如果是sender/receiver，那就匹配port_prototype
        for port_info in asw_cfg[port_swc][swc_port_key].values():
            if "server" in port_info["type"].lower():
                if port_info["name"].rsplit("_", 1)[0] == port_ref.split("/")[-1]:
                    port_type = port_info["type"]
                    break
            elif "client" in port_info["type"].lower():
                if port_info["path"] == port_ref:
                    port_type = port_info["type"]
                    break
            elif "sender" in port_info["type"].lower() or "receiver" in port_info["type"].lower():
                if port_info["port_prototype"] == port_ref.split("/")[-1]:
                    port_type = port_info["type"]
                    native_category = port_info["arg"]["datatype"]["native_category"]
                    category = native_category
                    if native_category == "NUMERICAL":
                        fake_data_type = port_info["arg"]["datatype"]["basetype"]
                        data_type = idts.get(fake_data_type, {}).get("basetype", None)
                        data_size = 1
                    elif native_category == "ARRAY":
                        fake_data_type = port_info["arg"]["datatype"]["basetype"]
                        data_type = idts.get(fake_data_type, {}).get("basetype", None)
                        data_size = port_info["arg"]["datatype"]["size"]
                    elif native_category == "STRUCTURE":
                        for member in port_info["arg"]["datatype"]["members"]:
                            fake_data_type = member["datatype"]
                            data_type = idts.get(fake_data_type, {}).get("basetype", None)
                            struct_member_list.append(data_type)
                    break
            elif "modeswitch" in port_info["type"].lower() or "modenotification" in port_info["type"].lower():
                if port_info["port_name"] == port_ref.split("/")[-1]:
                    port_type = port_info["type"]
                    break

        if not port_type:
            pass

        # print(f"port_swc:{port_swc}")
        # NOTE：存在一些特殊场景，eg：类型似乎为server但是通过name却匹配不到port_ref...
        return is_swc_ok, port_type, category, data_type, data_size, struct_member_list

    @classmethod
    def get_basic_data_type_size(cls, data_type):
        type_size = 0
        if data_type.lower() == "boolean":
            type_size = 8
        else:
            numbers = re.findall(r"\d+", data_type)
            if len(numbers) == 1:
                type_size = int(numbers[0])
        return type_size

    @classmethod
    def task_mapping_instance_is_constructed(cls, task_mapping_instance):
        return task_mapping_instance is not None

    @classmethod
    def check_asw_config_data(cls, asw_cfg):
        return asw_cfg is not None

    @classmethod
    def get_runnable_dict(cls, root_item):
        runnable_dict = {}
        for category_name, category_instance in root_item.child_map.items():
            if category_name not in runnable_dict:
                runnable_dict.update({category_name: {}})
            for swc_name, swc_instance in category_instance.child_map.items():
                if swc_name not in runnable_dict[category_name]:
                    runnable_dict[category_name].update({swc_name: {}})
                for runnable_item in swc_instance.child_items:
                    if not runnable_item or not runnable_item.data:
                        continue
                    if "RunnableName" not in runnable_item.data:
                        continue
                    runnable_name = runnable_item.data["RunnableName"]
                    runnable_instance = runnable_dict[category_name][swc_name].get(runnable_name)
                    if runnable_instance is None:
                        runnable_instance = {
                            "trigger_event_list": [],
                            "mapped_status": runnable_item.mapped,
                            "event_ref": runnable_item.data["EventRef"],
                            "has_no_port_event": False,
                        }
                        runnable_dict[category_name][swc_name].update({runnable_name: runnable_instance})
                    runnable_instance["trigger_event_list"].append(runnable_item.data["TriggerEvent"])

        # NOTE: service components中一般只有两种trigger event，timing(与schedule entity关联)和operation（server runnble）
        category_name_list = ["Application Components"]
        port_event_list = [
            "DataReceivedEvent",
            "DataReceivedErrorEvent",
            "DataSendCompletedEvent",
            "DataWriteCompletedEvent",
            "OperationInvokedEvent",
            "AsynchronousServerCallReturnsEvent",
            "ExternalTriggerOccurredEvent",
        ]
        for category_name, category_instance in runnable_dict.items():
            if category_name not in category_name_list:
                continue
            for swc_name, swc_instance in category_instance.items():
                for runnable_name, runnable_instance in swc_instance.items():
                    trigger_event_list = runnable_dict[category_name][swc_name][runnable_name]["trigger_event_list"]
                    other_event_list = [i for i in trigger_event_list if i not in port_event_list]
                    if len(other_event_list) > 0:
                        runnable_dict[category_name][swc_name][runnable_name]["has_no_port_event"] = True

        return runnable_dict

    @classmethod
    def get_swc_core_dict(cls, task_mapping_instance):
        swc_core_dict = {"Application Components": {}, "Service Components": {}, "Schedulable Entities": {}}
        if not task_mapping_instance or not task_mapping_instance.item_list:
            return swc_core_dict

        col_count = task_mapping_instance.get_col_count()
        table_size = len(task_mapping_instance.item_list)
        for i in range(table_size - 1, -1, -1):
            table_item = task_mapping_instance.get_item(i)
            if not table_item or not table_item.item_data:
                continue
            cur_col = i % col_count
            task_info = task_mapping_instance.get_task_info_by_col(cur_col)
            # PC / incomplete OsTask headers may omit CoreId — skip rather than KeyError.
            if (not task_info) or (not hasattr(task_info, "get")) or ("CoreId" not in task_info):
                continue
            core_id = task_info["CoreId"]
            item_data = table_item.item_data
            bind_item_list = task_mapping_instance.get_bind_item_list(item_data)
            for j, bind_item in enumerate(bind_item_list):
                is_service_component = bind_item.data["IsServiceComponent"]
                is_main_function = bind_item.data["IsMainFunction"]
                swc_name = bind_item.data["Component"]

                category_name = None
                if not is_service_component and not is_main_function:
                    category_name = "Application Components"
                elif is_service_component and is_main_function:
                    category_name = "Service Components"
                elif not is_service_component and is_main_function:
                    category_name = "Schedulable Entities"
                if not category_name:
                    continue

                core_id_list = swc_core_dict[category_name].get(swc_name)
                if core_id_list is None:
                    swc_core_dict[category_name].update({swc_name: []})
                core_id_list = swc_core_dict[category_name].get(swc_name)
                if core_id not in core_id_list:
                    core_id_list.append(core_id)

        return swc_core_dict

    @classmethod
    def get_swc_runnable_core_dict(cls, task_mapping_instance):
        swc_core_dict = {"Application Components": {}, "Service Components": {}, "Schedulable Entities": {}}
        if not task_mapping_instance or not task_mapping_instance.item_list:
            return swc_core_dict

        col_count = task_mapping_instance.get_col_count()
        table_size = len(task_mapping_instance.item_list)
        for i in range(table_size - 1, -1, -1):
            table_item = task_mapping_instance.get_item(i)
            if not table_item or not table_item.item_data:
                continue
            cur_col = i % col_count
            task_info = task_mapping_instance.get_task_info_by_col(cur_col)
            if (not task_info) or (not hasattr(task_info, "get")) or ("CoreId" not in task_info):
                continue
            core_id = task_info["CoreId"]
            item_data = table_item.item_data
            bind_item_list = task_mapping_instance.get_bind_item_list(item_data)
            for j, bind_item in enumerate(bind_item_list):
                is_service_component = bind_item.data["IsServiceComponent"]
                is_main_function = bind_item.data["IsMainFunction"]
                swc_name = bind_item.data["Component"]
                runnable_name = bind_item.data["RunnableName"]
                eventref = bind_item.data["EventRef"]

                category_name = None
                if not is_service_component and not is_main_function:
                    category_name = "Application Components"
                elif is_service_component and is_main_function:
                    category_name = "Service Components"
                elif not is_service_component and is_main_function:
                    category_name = "Schedulable Entities"
                if not category_name:
                    continue

                core_id_list = swc_core_dict[category_name].get(swc_name)
                if core_id_list is None:
                    swc_core_dict[category_name].update({swc_name: []})
                core_id_list = swc_core_dict[category_name].get(swc_name)
                core_entry = {"RunnableName": runnable_name, "CoreId": core_id, "EventRef": eventref}
                if core_entry not in core_id_list:
                    core_id_list.append(core_entry)
        return swc_core_dict

    @classmethod
    def get_cs_runnable_list(cls, mapped_ports, asw_cfg):
        cs_runnable_list = []
        if not mapped_ports:
            return cs_runnable_list
        for port_mapping_item in mapped_ports.values():
            cs_runnable_dict = {}
            if "provider_iref" not in port_mapping_item.keys() or "requester_iref" not in port_mapping_item.keys():
                continue
            pport_category_name, pport_swc_name, pport_type, pport_runnable = cls.get_cs_port_info(
                port_mapping_item, "provider_iref", asw_cfg
            )
            rport_category_name, rport_swc_name, rport_type, rport_runnable = cls.get_cs_port_info(
                port_mapping_item, "requester_iref", asw_cfg
            )
            # 可忽略，因为RTE112001已覆盖
            if not pport_swc_name or not rport_swc_name or not pport_category_name or not rport_category_name:
                continue

            # NOTE:可忽略,增加warnning校验规则
            if not pport_type or not rport_type:
                continue

            if "server" not in pport_type.lower() or "client" not in rport_type.lower():
                continue

            cs_runnable_dict.update({"pport_category_name": pport_category_name})
            cs_runnable_dict.update({"pport_swc_name": pport_swc_name})
            cs_runnable_dict.update({"pport_type": pport_type})
            cs_runnable_dict.update({"pport_runnable": pport_runnable})
            cs_runnable_dict.update({"rport_category_name": rport_category_name})
            cs_runnable_dict.update({"rport_swc_name": rport_swc_name})
            cs_runnable_dict.update({"rport_type": rport_type})
            cs_runnable_dict.update({"rport_runnable": rport_runnable})

            cs_runnable_list.append(cs_runnable_dict)
        return cs_runnable_list

    @classmethod
    def get_sr_runnable_list(cls, mapped_ports, asw_cfg):
        sr_runnable_list = []
        if not mapped_ports:
            return sr_runnable_list
        for port_mapping_item in mapped_ports.values():
            sr_runnable_dict = {}
            if "provider_iref" not in port_mapping_item.keys() or "requester_iref" not in port_mapping_item.keys():
                continue
            pport_category_name, pport_swc_name, pport_type, pport_runnable_list = cls.get_sr_port_info(
                port_mapping_item, "provider_iref", asw_cfg
            )
            rport_category_name, rport_swc_name, rport_type, rport_runnable_list = cls.get_sr_port_info(
                port_mapping_item, "requester_iref", asw_cfg
            )
            # 可忽略，因为RTE112001已覆盖
            if not pport_swc_name or not rport_swc_name or not pport_category_name or not rport_category_name:
                continue

            # NOTE:可忽略,增加warnning校验规则
            if not pport_type or not rport_type:
                continue

            if "sender" not in pport_type.lower() or "receiver" not in rport_type.lower():
                continue

            sr_runnable_dict.update({"pport_category_name": pport_category_name})
            sr_runnable_dict.update({"pport_swc_name": pport_swc_name})
            sr_runnable_dict.update({"pport_type": pport_type})
            sr_runnable_dict.update({"pport_runnable_list": pport_runnable_list})
            sr_runnable_dict.update({"rport_category_name": rport_category_name})
            sr_runnable_dict.update({"rport_swc_name": rport_swc_name})
            sr_runnable_dict.update({"rport_type": rport_type})
            sr_runnable_dict.update({"rport_runnable_list": rport_runnable_list})

            sr_runnable_list.append(sr_runnable_dict)
        return sr_runnable_list

    @classmethod
    def get_cs_port_info(cls, port_mapping_item, port_key, asw_cfg):
        # client/server
        category_name = None
        swc_name = None
        port_type = None
        runnable = None

        swc_name = port_mapping_item[port_key]["context_component_ref"].split("/")[-1]
        if swc_name not in asw_cfg:
            swc_name = None
            # logger.warning(f"{port_swc} not in asw_cfg!")
            return category_name, swc_name, port_type, runnable

        if asw_cfg[swc_name]["type"] == "APPLICATION-SW-COMPONENT-TYPE":
            category_name = "Application Components"
        elif asw_cfg[swc_name]["type"] == "SERVICE-SW-COMPONENT-TYPE":
            category_name = "Service Components"

        port_ref_key = "target_pport_ref" if port_key == "provider_iref" else "target_rport_ref"
        swc_port_key = "pports" if port_key == "provider_iref" else "rports"
        port_ref = port_mapping_item[port_key][port_ref_key]
        # 如果是server，那就匹配名称; 如果是client，那就匹配path; 如果是sender/receiver，那就匹配port_prototype
        for port_info in asw_cfg[swc_name][swc_port_key].values():
            if "server" in port_info["type"].lower():
                if port_info["name"].rsplit("_", 1)[0] == port_ref.split("/")[-1]:
                    port_type = port_info["type"]
                    runnable = port_info["runnable"]
                    break
            elif "client" in port_info["type"].lower():
                if port_info["path"] == port_ref:
                    port_type = port_info["type"]
                    runnable = port_info["runnable"]
                    break

        return category_name, swc_name, port_type, runnable

    @classmethod
    def get_sr_port_info(cls, port_mapping_item, port_key, asw_cfg):
        # client/server
        category_name = None
        swc_name = None
        port_type = None
        runnable = None

        swc_name = port_mapping_item[port_key]["context_component_ref"].split("/")[-1]
        if swc_name not in asw_cfg:
            swc_name = None
            # logger.warning(f"{port_swc} not in asw_cfg!")
            return category_name, swc_name, port_type, runnable

        if asw_cfg[swc_name]["type"] == "APPLICATION-SW-COMPONENT-TYPE":
            category_name = "Application Components"
        elif asw_cfg[swc_name]["type"] == "SERVICE-SW-COMPONENT-TYPE":
            category_name = "Service Components"

        port_ref_key = "target_pport_ref" if port_key == "provider_iref" else "target_rport_ref"
        swc_port_key = "pports" if port_key == "provider_iref" else "rports"
        port_ref = port_mapping_item[port_key][port_ref_key]
        # 如果是server，那就匹配名称; 如果是client，那就匹配path; 如果是sender/receiver，那就匹配port_prototype
        runnable_list = []
        for port_info in asw_cfg[swc_name][swc_port_key].values():
            port_type = port_info.get("type")
            if not port_type:
                continue

            if "sender" in port_type.lower() or "receiver" in port_type.lower():
                if port_info["port_prototype"] == port_ref.split("/")[-1]:
                    runnable = port_info.get("runnable")
                    if not runnable:
                        continue
                    if isinstance(runnable, str):
                        runnable_list = [runnable]
                    elif isinstance(runnable, list):
                        runnable_list = runnable
                    break

        return category_name, swc_name, port_type, runnable_list

    @classmethod
    def get_mapped_info(cls, category_name, swc_name, runnable, runnable_dict):
        ret_value = False
        mapped_status = False
        event_ref = None
        trigger_event_list = []
        if (
            category_name not in runnable_dict
            or swc_name not in runnable_dict[category_name]
            or runnable not in runnable_dict[category_name][swc_name]
        ):
            return ret_value, mapped_status, event_ref, trigger_event_list

        ret_value = True
        mapped_status = runnable_dict[category_name][swc_name][runnable]["mapped_status"]
        event_ref = runnable_dict[category_name][swc_name][runnable]["event_ref"]
        trigger_event_list = runnable_dict[category_name][swc_name][runnable]["trigger_event_list"]

        return ret_value, mapped_status, event_ref, trigger_event_list

    @classmethod
    def get_core_id_list(cls, category_name, swc_name, swc_core_dict):
        ret_value = False
        core_id_list = None
        if category_name not in swc_core_dict:
            return ret_value, core_id_list
        if swc_name not in swc_core_dict[category_name]:
            return ret_value, core_id_list

        ret_value = True
        core_id_list = swc_core_dict[category_name][swc_name]
        return ret_value, core_id_list

    @classmethod
    def get_runnable_name_in_asw(cls, rte_event_ref: str, autosar_asw_class):
        """get runnable name in application component by rte event ref"""
        runnable_name = None
        runnable_info = autosar_asw_class.find(rte_event_ref)
        if not runnable_info:
            return runnable_name

        runnable_name = getattr(getattr(runnable_info, "START_ON_EVENT_REF", None), "valueOf_", "").split("/")[-1]

        return runnable_name

    @classmethod
    def get_task_mapping_info_by_task_name(cls, task_name, task_mapping_inst):
        '''
            通过 task 名称, 从task mapping 单元格中获取 task mapping 详细信息
            :param task_name: 任务名称
            :param task_mapping_inst: task mapping 实例
            :return: task mapping 信息列表，包括 runnable 名称和所在位置, 绑定的 event 以及 component
        '''
        task_mapping_info = []
        if task_mapping_inst is None or not task_name:
            return task_mapping_info
        col_idx = task_mapping_inst.get_col_by_task_name(task_name)
        # Autostart tasks are excluded from mapping table headers (get_sorted_tasks);
        # treat missing column as no mapping rows instead of TypeError on int+None.
        if col_idx is None:
            return task_mapping_info
        row_cnt, col_cnt = task_mapping_inst.get_row_count(), task_mapping_inst.get_col_count()
        for row_idx in range(row_cnt):
            if not (table_item := task_mapping_inst.get_item(row_idx * col_cnt + col_idx)) or not table_item.item_data:
                continue
            bind_item_list = task_mapping_inst.get_bind_item_list(table_item.item_data)

            for bind_item in bind_item_list:
                task_mapping_info.append({
                    "posistion": row_idx,
                    "Component": bind_item.data['Component'],
                    "EventRef": bind_item.data['EventRef'],
                    "RunnableName": bind_item.data['RunnableName']
                })

        return task_mapping_info


class ResultLevel(IntEnum):
    # Error--Result_Err
    # Warning--Result_Warn
    # NoError--Result_OK
    Result_Err = -2
    Result_Warn = -1
    Result_OK = 0


class Compatibility(IntEnum):
    not_match = 0
    partial_match = 1
    full_match = 2
