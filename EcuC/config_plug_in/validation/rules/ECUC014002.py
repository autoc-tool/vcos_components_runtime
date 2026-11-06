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


# PduLengthTypeEnum 附加校验
class EcuC014002Rule(BasicRule):
    ruleset_name = "ECUC014002"

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Validation Of PduLengthTypeEnum"

    @timing_decorator
    def validation_run(self):

        # 1）准备校验数据并依次校验
        param_path = "/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection/PduLengthTypeEnum"
        ecuc_ecuc_dict = self.bsw_ecuc_cfg_class_dict["EcuC"]["ArPackages"]["ActiveEcuC"]["EcuC"]
        ecuc_pdu_collection = ecuc_ecuc_dict.get("EcucConfigSet", {}).get("EcucPduCollection", {})
        pdu_length_type_enum = ecuc_pdu_collection.get("PduLengthTypeEnum", {}).get("Value", None)

        for pdu_name, pdu_info in ecuc_pdu_collection.items():
            if not isinstance(pdu_info, dict):
                continue
            if not pdu_info.get("DefinitionRef", "").endswith("Pdu"):
                continue
            pdu_length = pdu_info.get("PduLength", {}).get("Value", None)
            if not isinstance(pdu_length, int):
                continue
            if pdu_length > 65536:
                if pdu_length_type_enum != "UINT32":
                    self.vlog(
                        self.validation_code,
                        self.validation_summary,
                        f"Pdu({pdu_name}) length more than 65536, PduLengthTypeEnum must be set to UINT32!",
                        param_path,
                        "fail",
                    )
                    return
            elif pdu_length > 256:
                if pdu_length_type_enum not in ["UINT16", "UINT32"]:
                    self.vlog(
                        self.validation_code,
                        self.validation_summary,
                        f"Pdu({pdu_name}) length more than 256, PduLengthTypeEnum must be set to UINT16 or UINT32!",
                        param_path,
                        "fail",
                    )
                    return
        self.vlog(self.validation_code, self.validation_summary, "PduLengthTypeEnum pass", param_path, "pass")
