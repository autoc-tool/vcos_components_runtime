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
from func_module.module_management.arxml_handler.com_stack_ecuc.com_stack_ecuc_base_class import (
    ComStackEcucBaseClass,
)
from basic_func_module.autosar_utils.utils import get_definition_ref
from basic_func_module.autosar_utils.autosar_util import AutosarUtil
from func_module.health_monitor.logger import logger


class EcuCEcucManager(ComStackEcucBaseClass):

    def __init__(self):
        sort_path_list = ["/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection"]
        super().__init__("EcuC", sort_path_list)

    def get_new_ecuc_from_different_initial(
        self, old_initial, new_initial, autosar_ecuc
    ):
        logger.info("Start updating Ecuc_ecuc.arxml from initial!")
        ecuc_autosar = super().get_new_ecuc_from_different_initial(
            old_initial, new_initial, autosar_ecuc
        )

        pdus = ecuc_autosar.find("/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection")
        if not pdus:
            return ecuc_autosar

        for pdu in pdus.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
            if not get_definition_ref(pdu).endswith("Pdu"):
                continue
            if not hasattr(pdu, "REFERENCE_VALUES") or not pdu.REFERENCE_VALUES:
                continue

            core_refs = []
            for ref in pdu.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
                if not get_definition_ref(ref).endswith("EcucPduDefaultCoreRef"):
                    continue
                core_refs.append(ref)
            if len(core_refs) < 2:
                continue
            core_ref_to_keep = None
            for ref in reversed(core_refs):
                if AutosarUtil.is_auto_derived(ref):
                    core_ref_to_keep = ref
                    break
            if not core_ref_to_keep:
                core_ref_to_keep = core_refs[-1]

            for ref in pdu.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
                if (
                    not get_definition_ref(ref).endswith("EcucPduDefaultCoreRef")
                    or ref == core_ref_to_keep
                ):
                    continue
                pdu.REFERENCE_VALUES.ECUC_REFERENCE_VALUE.remove(ref)
        return ecuc_autosar
