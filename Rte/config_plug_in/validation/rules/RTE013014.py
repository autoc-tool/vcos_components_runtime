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


# 互斥校验：对于有S/R Port连接的runnable，要求双方必须是mapped状态
class Rte013014Rule(BasicRule):
    ruleset_name = "RTE013014"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "In S/R comunication, the sender and receiver runnable should be mapped"

        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data

        self.mapped_ports = rte_common_data.get_mapped_ports()
        self.asw_cfg = rte_common_data.get_asw_cfg()
        self.root_item = rte_common_data.get_root_item()

        self.runnable_dict = RteUtils.get_runnable_dict(self.root_item)

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        return RteUtils.check_asw_config_data(self.asw_cfg)

    @timing_decorator
    def validation_run(self):
        sender_port_event_list = ['DataSendCompletedEvent', 'DataWriteCompletedEvent']
        receiver_port_event_list = ['DataReceivedEvent', 'DataReceivedErrorEvent']

        for sr_runnable in RteUtils.get_sr_runnable_list(self.mapped_ports, self.asw_cfg):
            pport_category_name = sr_runnable['pport_category_name']
            pport_swc_name = sr_runnable['pport_swc_name']
            pport_runnable_list = sr_runnable['pport_runnable_list']

            rport_category_name = sr_runnable['rport_category_name']
            rport_swc_name = sr_runnable['rport_swc_name']
            rport_runnable_list = sr_runnable['rport_runnable_list']

            for pport_runnable in pport_runnable_list:
                pret, prunnable_status, pparam_path, ptrigger_event_list = RteUtils.get_mapped_info(
                    pport_category_name, pport_swc_name, pport_runnable, self.runnable_dict)
                check_sender_trigger = any(i in sender_port_event_list for i in ptrigger_event_list)
                if not pret or not check_sender_trigger:
                    continue
                message = f"pport information: swc category = {pport_category_name}; swc name = {pport_swc_name}; runnable name = {pport_runnable}; mapping status = {prunnable_status}",
                if not prunnable_status:
                    self.vlog(self.validation_code, self.validation_summary, message, pparam_path, "fail")
                else:
                    self.vlog(self.validation_code, self.validation_summary, message, pparam_path, "pass")

            for rport_runnable in rport_runnable_list:
                rret, rrunnable_status, rparam_path, rtrigger_event_list = RteUtils.get_mapped_info(
                    rport_category_name, rport_swc_name, rport_runnable, self.runnable_dict)
                check_receiver_trigger = any(i in receiver_port_event_list for i in rtrigger_event_list)

                if not rret or not check_receiver_trigger:
                    continue
                message = f"rport information: swc category = {rport_category_name}; swc name = {rport_swc_name}; runnable name = {rport_runnable}; mapping status = {rrunnable_status}",
                if not rrunnable_status:
                    self.vlog(self.validation_code, self.validation_summary, message, rparam_path, "fail")
                else:
                    self.vlog(self.validation_code, self.validation_summary, message, rparam_path, "pass")
