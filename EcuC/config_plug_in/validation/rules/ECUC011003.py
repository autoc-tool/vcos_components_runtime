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


# EcucPartitionBswModuleExecution 重复校验
class EcuC011003Rule(BasicRule):
    ruleset_name = "ECUC011003"
    validation_result = False

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Validation Of EcucPartitionBswModuleExecution"
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

                @lang.when_all((+lang.m.bsw_module_execution))
                def fact(c):
                    self.__class__.validation_result = True

            pass

    @timing_decorator
    def validation_run(self):
        validation_data_list = []

        # 1）准备校验数据并依次校验
        ecuc_partition_collection = (
            self.bsw_ecuc_cfg_class_dict.get("EcuC", {})
            .get("ArPackages", {})
            .get("ActiveEcuC", {})
            .get("EcuC", {})
            .get("EcucPartitionCollection", None)
        )
        if ecuc_partition_collection is None:
            return
        for partition_name, partition in ecuc_partition_collection.items():
            if not isinstance(partition, dict):
                continue
            if partition.get("DefinitionRef", "").split("/")[-1] != "EcucPartition":
                continue
            if partition.get("EcucPartitionBswModuleExecution", {}).get("Value", False) is not True:
                continue

            base_path = "/ActiveEcuC/EcuC/EcucPartitionCollection"
            param_path = f"{base_path}/{partition_name}/EcucPartitionBswModuleExecution"
            validation_data = {}
            validation_data["bsw_module_execution"] = True
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
                    "EcucPartitionBswModuleExecution pass",
                    param_path,
                    "pass",
                )
            else:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    "EcucPartitionBswModuleExecution implemented by multiple partitions",
                    param_path,
                    "fail",
                )

        # 2）清空ruleset中的所有fact，为下一次校验做准备
        if validation_data_list:
            lang.retract_facts(self.__class__.ruleset_name, validation_data_list)
        pass
