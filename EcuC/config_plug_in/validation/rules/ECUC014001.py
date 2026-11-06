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


# PduIdTypeEnum 附加校验
class EcuC014001Rule(BasicRule):
    ruleset_name = "ECUC014001"

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Validation Of PduIdTypeEnum"

    @timing_decorator
    def validation_run(self):

        # 1）准备校验数据并依次校验
        param_path = "/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection/PduIdTypeEnum"
        ecuc_ecuc_dict = self.bsw_ecuc_cfg_class_dict["EcuC"]["ArPackages"]["ActiveEcuC"]["EcuC"]
        pdu_id_type_enum = (
            ecuc_ecuc_dict.get("EcucConfigSet", {})
            .get("EcucPduCollection", {})
            .get("PduIdTypeEnum", {})
            .get("Value", None)
        )
        pdur_dict = (
            self.bsw_ecuc_cfg_class_dict.get("PduR", {}).get("ArPackages", {}).get("ActiveEcuC", {}).get("PduR", {})
        )
        pdur_routing_path_count = _get_pdu_num(pdur_dict)
        if not isinstance(pdur_routing_path_count, int):
            result = True
        elif pdu_id_type_enum == "UINT16":
            result = True
        elif pdur_routing_path_count <= 256:
            result = True
        else:
            result = False

        if result:
            self.vlog(self.validation_code, self.validation_summary, "PduIdTypeEnum pass", param_path, "pass")
        else:
            self.vlog(
                self.validation_code,
                self.validation_summary,
                "PduR module handles more than 256 PDUs, PduIdTypeEnum must be set to UINT16!",
                param_path,
                "fail",
            )


def _get_pdu_num(pdur_dict):
    num = 0
    if not isinstance(pdur_dict, dict):
        return num
    for pdu in pdur_dict.get("PduRRoutingPaths", {}).values():
        if not isinstance(pdu, dict):
            continue
        if pdu.get("DefinitionRef", "").split("/")[-1] != "PduRRoutingPath":
            continue
        num += 1
    return num
