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
from durable import lang


# EcucCoreHwRef 重复校验
class EcuC011002Rule(BasicRule):
    ruleset_name = "ECUC011002"
    validation_result = False

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Validation Of EcucCoreHwRef"
        self.durable_init()

    def durable_init(self):
        # 注：固定名称的规则集只能初始化一次，否则会异常报错
        try:
            lang.get_host().get_ruleset(self.__class__.ruleset_name)
        except Exception:
            # print("get_ruleset() exception message: {0}".format(e.args))
            with lang.ruleset(self.__class__.ruleset_name):

                @lang.when_all(+lang.m.status)
                def event(c):
                    pass

                @lang.when_all((+lang.m.ecuc_core_hw_ref))
                def fact(c):
                    self.__class__.validation_result = True

            pass

    @timing_decorator
    def validation_run(self):
        validation_data_list = []

        # 1）准备校验数据并依次校验
        ecuc_hardware_dict = self.bsw_ecuc_cfg_class_dict["EcuC"]["ArPackages"]["ActiveEcuC"]["EcuC"].get(
            "EcucHardware", {}
        )
        for hardware_name, hardware_info in ecuc_hardware_dict.items():
            if not isinstance(hardware_info, dict):
                continue
            ecuc_core_hw_ref = hardware_info.get("EcucCoreHwRef", {}).get("ValueRef", None)
            if ecuc_core_hw_ref in [None, ""]:
                continue
            base_path = "/ActiveEcuC/EcuC/EcucHardware"
            param_path = f"{base_path}/{hardware_name}/EcucCoreHwRef"
            validation_data = {}
            validation_data["ecuc_core_hw_ref"] = ecuc_core_hw_ref
            validation_data_list.append(validation_data)

            try:
                self.__class__.validation_result = False
                lang.assert_fact(self.__class__.ruleset_name, validation_data)
            except Exception:
                self.__class__.validation_result = False
                # print("assert_fact() exception message {0}".format(e.args))
                pass

            if self.__class__.validation_result:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    f"EcucCoreDefinition:{hardware_name}, EcucCoreHwRef:({ecuc_core_hw_ref}) pass",
                    param_path,
                    "pass",
                )
            else:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    f"EcucCoreDefinition:{hardware_name}, EcucCoreHwRef({ecuc_core_hw_ref}) is duplicated!",
                    param_path,
                    "fail",
                )

        # 2）清空ruleset中的所有fact，为下一次校验做准备
        if validation_data_list:
            lang.retract_facts(self.__class__.ruleset_name, validation_data_list)
        pass
