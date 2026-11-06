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


# Trigger类型校验：当前只支持STANDARD类型的Trigger
class Rte113006Rule(BasicRule):
    ruleset_name = "RTE113006"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The queued internal/external trigger is not supported"
        self.asw_cfg = rte_common_data.get_asw_cfg()

    @timing_decorator
    def validation_run(self):
        for swc, swc_value in self.asw_cfg.items():
            for runnable, runnable_value in swc_value['runnables'].items():
                for it in runnable_value['internal_trigger']:
                    trigger_runnable = it['trigger_runnable']
                    trigger_point = it['trigger_point']
                    trigger_type = it['trigger_type']
                    if it['trigger_type'] != 'STANDARD':
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"internal trigger, trigger_runnable: {trigger_runnable}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                            f"{swc}/{runnable}/{trigger_point}", "fail")
                    else:
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"internal trigger, trigger_runnable: {trigger_runnable}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                            f"{swc}/{runnable}/{trigger_point}", "pass")

            for pport_trigger, pport_value in swc_value['pports'].items():
                if pport_value['type'] != 'External Trigger':
                    continue
                pport = pport_value['port_prototype']
                trigger_point = pport_value['data_element']
                trigger_type = pport_value.get('data_element_type', 'STANDARD')
                if trigger_type != 'STANDARD':
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"external trigger, pport: {pport}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                        f"{swc}/{pport_trigger}", "fail")
                else:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"external trigger, pport: {pport}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                        f"{swc}/{pport_trigger}", "pass")

            for rport_trigger, rport_value in swc_value['rports'].items():
                if rport_value['type'] != 'External Trigger':
                    continue
                rport = rport_value['port_prototype']
                trigger_point = rport_value['data_element']
                trigger_type = rport_value.get('data_element_type', 'STANDARD')
                if trigger_type != 'STANDARD':
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"external trigger, rport: {rport}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                        f"{swc}/{rport_trigger}", "fail")
                else:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"external trigger, rport: {rport}, trigger_point: {trigger_point}, has_trigger_type: {trigger_type}",
                        f"{swc}/{rport_trigger}", "pass")
