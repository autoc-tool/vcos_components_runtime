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
from .Rte_common import RteCommonData, RteUtils
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：跨核C/S通信，要求server runnable必须是mapped状态
class Rte013019Rule(BasicRule):
    ruleset_name = "RTE013019"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "In multicore C/S comunication, the server runnable should be mapped"
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data

        self.mapped_ports = rte_common_data.get_mapped_ports()
        self.asw_cfg = rte_common_data.get_asw_cfg()
        self.root_item = rte_common_data.get_root_item()
        task_mapping_instance = self.rte_common_data.get_task_mapping_instance()

        self.runnable_dict = RteUtils.get_runnable_dict(self.root_item)
        self.swc_core_dict = RteUtils.get_swc_core_dict(task_mapping_instance)

        pass

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        if not RteUtils.task_mapping_instance_is_constructed(self.rte_common_data.task_mapping_instance):
            return False
        return RteUtils.check_asw_config_data(self.asw_cfg)

    @timing_decorator
    def validation_run(self):
        server_port_event_list = ['OperationInvokedEvent', 'AsynchronousServerCallReturnsEvent']

        for cs_runnable in RteUtils.get_cs_runnable_list(self.mapped_ports, self.asw_cfg):
            pport_category_name = cs_runnable['pport_category_name']
            pport_swc_name = cs_runnable['pport_swc_name']
            pport_runnable = cs_runnable['pport_runnable']

            rport_category_name = cs_runnable['rport_category_name']
            rport_swc_name = cs_runnable['rport_swc_name']
            rport_runnable = cs_runnable['rport_runnable']

            _, pport_core_id_list = RteUtils.get_core_id_list(pport_category_name, pport_swc_name, self.swc_core_dict)
            _, rport_core_id_list = RteUtils.get_core_id_list(rport_category_name, rport_swc_name, self.swc_core_dict)

            # core id不唯一，有其他校验规则跟踪
            pcore_id = None
            if pport_core_id_list and len(pport_core_id_list) == 1:
                pcore_id = pport_core_id_list[0]

            rcore_id = None
            if rport_core_id_list and len(rport_core_id_list) == 1:
                rcore_id = rport_core_id_list[0]

            # core id相同，有其他校验规则跟踪
            if pcore_id and rcore_id and pcore_id == rcore_id:
                continue
            # core_id为空或core_id不相同，有其他校验规则跟踪
            if not pcore_id:
                continue
            # NOTE:只需要考虑server runnable, client要么是non-port, 要么是operation(实际触发源是其他runnable)
            pret, prunnable_status, pparam_path, ptrigger_event_list = RteUtils.get_mapped_info(
                pport_category_name, pport_swc_name, pport_runnable, self.runnable_dict)
            check_server_trigger = any(i in server_port_event_list for i in ptrigger_event_list)
            if not pret or not pparam_path or not check_server_trigger:
                continue

            # 格式："错误码", "摘要", "错误信息", "错误索引路径" "结果"
            message = f"pcore_id: {pcore_id}, rcore_id: {rcore_id}, pport runnable(category: {pport_category_name}, swc name:{pport_swc_name}, runnable name: {pport_runnable}, mapping status: {prunnable_status})",
            if not prunnable_status:
                self.vlog(self.validation_code, self.validation_summary, message, pparam_path, "fail")
            else:
                self.vlog(self.validation_code, self.validation_summary, message, pparam_path, "pass")
