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
"""ECUC014003: each Ecuc Pdu must configure EcucPduDefaultCoreRef (CanIf codegen hard-depends).

BSWMD lower=0, but CanIf filter reads ["EcucPduDefaultCoreRef"]["ValueRef"] for every Pdu
present in EcucPduCollection. Do not invent Core0 in the filter — fail at verify instead.
"""
from func_module.validation.common.basic_rule import BasicRule, timing_decorator
from durable.lang import *
from durable.engine import *


def _has_core_ref(pdu: dict) -> bool:
    node = pdu.get("EcucPduDefaultCoreRef") if isinstance(pdu, dict) else None
    if not isinstance(node, dict):
        # also accept DefinitionRef-suffixed sibling
        for k, v in (pdu or {}).items():
            if k in ("DefinitionRef", "Tag") or not isinstance(v, dict):
                continue
            dref = v.get("DefinitionRef", "")
            if isinstance(dref, str) and dref.split("/")[-1] == "EcucPduDefaultCoreRef":
                node = v
                break
    if not isinstance(node, dict):
        return False
    ref = node.get("ValueRef")
    return ref is not None and str(ref).strip() != ""


class EcuC014003Rule(BasicRule):
    ruleset_name = "ECUC014003"
    validation_result = False

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = (
            "Ecuc Pdu must have EcucPduDefaultCoreRef "
            "(CanIf codegen requires it; configure core ref, do not invent in filter)"
        )
        self.durable_init()

    def durable_init(self):
        try:
            get_host().get_ruleset(self.__class__.ruleset_name)
        except Exception:
            with ruleset(self.__class__.ruleset_name):

                @when_all(+m.status)
                def event(c):
                    pass

                @when_all(+m.pdu_name)
                def fact(c):
                    self.__class__.validation_result = True

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC"], self.bsw_ecuc_cfg_class_dict):
            self.vlog(
                self.validation_code,
                self.validation_summary,
                "Data required for validation is missing",
                self.validation_summary,
                "fail",
            )
            return False
        return True

    @timing_decorator
    def validation_run(self):
        valid = True
        ecuc = (
            self.bsw_ecuc_cfg_class_dict.get("EcuC", {})
            .get("ArPackages", {})
            .get("ActiveEcuC", {})
            .get("EcuC", {})
        )
        collection = (
            ecuc.get("EcucConfigSet", {}).get("EcucPduCollection", {})
            if isinstance(ecuc, dict)
            else {}
        )
        if not isinstance(collection, dict):
            return True

        base_path = "/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection"
        for pdu_name, pdu in collection.items():
            if pdu_name in ("DefinitionRef", "Tag") or not isinstance(pdu, dict):
                continue
            dref = pdu.get("DefinitionRef", "")
            if not (isinstance(dref, str) and dref.split("/")[-1] == "Pdu"):
                continue
            path = f"{base_path}/{pdu_name}/EcucPduDefaultCoreRef"
            if _has_core_ref(pdu):
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    f"Pdu {pdu_name} has EcucPduDefaultCoreRef",
                    path,
                    "pass",
                )
            else:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    (
                        f"Pdu {pdu_name} missing EcucPduDefaultCoreRef at {path}; "
                        f"configure core reference (CanIf codegen requires it; "
                        f"do not invent in filter)"
                    ),
                    path,
                    "fail",
                )
                valid = False
        return valid
