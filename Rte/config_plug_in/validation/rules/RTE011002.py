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
from collections import defaultdict
from func_module.validation.common.basic_rule import BasicRule, timing_decorator
from basic_func_module.autosar_utils.utils import get_short_name
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


# 重复校验：不同SWC下的同名Runnables不能部署同一个OS Application的Task
# Comparison key = (runnable SYMBOL/shortName, OsApplication).
# Do NOT use durable assert_fact here: leftover facts / MessageObservedException
# produced false FAILs that listed unrelated different SYMBOLs as "same name".
class Rte011002Rule(BasicRule):
    ruleset_name = "RTE011002"
    validation_result = False
    _SWC_SUFFIX = "_EcuSwComposition"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = (
            "RTE011002: Runnables that share the same SYMBOL/shortName but live in different SWCs "
            "must not be mapped into tasks of the same OsApplication "
            "(rename the runnable SYMBOL, or map the SWCs to different OsApplications)."
        )

    @staticmethod
    def _normalize_swc(swc_name: str) -> str:
        if swc_name.endswith(Rte011002Rule._SWC_SUFFIX):
            return swc_name[: -len(Rte011002Rule._SWC_SUFFIX)]
        return swc_name

    def get_event_info_by_ref(self, event_ref):
        runnable_name = ""
        asw = self.asw_autosar_dict
        if asw is None:
            return runnable_name
        event = asw.find(event_ref)
        if not event:
            return runnable_name

        start_on_event_ref = event.START_ON_EVENT_REF.valueOf_
        runnable = event.find(start_on_event_ref)
        runnable_name = runnable.SYMBOL.valueOf_ if runnable.SYMBOL else get_short_name(runnable)

        return runnable_name

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        # 1）准备Os相关dict: task_name -> OsApplication
        ecuc_os_dict = self.bsw_ecuc_cfg_class_dict['Os']['ArPackages']['ActiveEcuC']['Os']
        task_info_dict = {}
        for os_key, os_instance in ecuc_os_dict.items():
            if not isinstance(os_instance, dict):
                continue
            if "OsApplication" not in os_instance['DefinitionRef']:
                continue

            if 'OsAppTaskRef' not in os_instance.keys():
                continue

            if isinstance(os_instance['OsAppTaskRef']['ValueRef'], list):
                for task_name in os_instance['OsAppTaskRef']['ValueRef']:
                    task_name = task_name.split("/")[-1]
                    task_info_dict[task_name] = os_key
            elif isinstance(os_instance['OsAppTaskRef']['ValueRef'], str):
                task_name = os_instance['OsAppTaskRef']['ValueRef'].split("/")[-1]
                task_info_dict[task_name] = os_key

        # 2）Collect mappings: key=(SYMBOL, OsApplication) -> parties
        # Dedup within one (normalized) SWC by SYMBOL so multi-events of same runnable don't self-collide.
        groups = defaultdict(list)  # (rn, app) -> list[{swc, swc_norm, path}]
        seen_in_swc = set()  # (swc_norm, rn, app)

        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            swc_name = rte_key
            swc_norm = self._normalize_swc(swc_name)
            for instance_key, instance_item in rte_instance.items():
                if not isinstance(instance_item, dict):
                    continue
                def_ref = instance_item.get('DefinitionRef') or ''
                # Application mapping only (substring does not match RteBswEventToTaskMapping)
                if 'RteEventToTaskMapping' not in def_ref:
                    continue

                mapped = instance_item.get('RteMappedToTaskRef') or {}
                task_ref = mapped.get('ValueRef')
                if not task_ref:
                    continue
                task_name = task_ref.split("/")[-1]
                if task_name not in task_info_dict:
                    continue
                application_name = task_info_dict[task_name]
                event_ref = (instance_item.get('RteEventRef') or {}).get('ValueRef')
                if not event_ref:
                    continue
                runnable_name = self.get_event_info_by_ref(event_ref)
                param_path = mapped.get('reference_item_path') or \
                    f"/ActiveEcuC/Rte/{swc_name}/{instance_key}/RteMappedToTaskRef"

                if not runnable_name:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        (
                            f"Cannot resolve RteEventRef '{event_ref}' to a runnable SYMBOL/shortName "
                            f"(SWC '{swc_name}', OsApplication '{application_name}'). "
                            f"Comparison key would be (SYMBOL=<unresolved>, OsApplication='{application_name}'). "
                            f"Fix: point RteEventRef at a valid TimingEvent/Runnable in ASW InternalBehavior."
                        ),
                        param_path, "fail", [],
                        [
                            f"Fix RteEventRef on '{param_path}' so it resolves to a runnable with a SYMBOL."
                        ],
                    )
                    continue

                dedup_key = (swc_norm, runnable_name, application_name)
                if dedup_key in seen_in_swc:
                    continue
                seen_in_swc.add(dedup_key)
                groups[(runnable_name, application_name)].append({
                    "swc_name": swc_name,
                    "swc_norm": swc_norm,
                    "param_path": param_path,
                })

        # 3）Validate groups
        for (rn, app), parties in groups.items():
            distinct_swcs = {}
            for p in parties:
                distinct_swcs.setdefault(p["swc_norm"], p)

            if len(distinct_swcs) < 2:
                # unique SYMBOL within this OsApplication (same SWC aliases collapsed)
                for p in parties:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        (
                            f"comparison_key=(SYMBOL='{rn}', OsApplication='{app}'); "
                            f"swc='{p['swc_name']}': unique in application."
                        ),
                        p["param_path"], "pass")
                continue

            # True collision: same SYMBOL in same OsApplication across different SWCs
            party_list = list(distinct_swcs.values())
            parties_txt = "; ".join(
                f"SWC '{p['swc_name']}' (path {p['param_path']})" for p in party_list
            )
            other_swcs = [p["swc_name"] for p in party_list]
            msg = (
                f"comparison_key=(SYMBOL='{rn}', OsApplication='{app}'): "
                f"the same runnable SYMBOL '{rn}' is mapped into OsApplication '{app}' "
                f"from {len(party_list)} different SWCs: {parties_txt}. "
                f"Fix by (1) renaming the runnable SYMBOL in one SWC InternalBehavior, "
                f"or (2) moving one SWC's task mapping to a different OsApplication "
                f"(change RteMappedToTaskRef / OsAppTaskRef ownership)."
            )
            solve = [
                f"Colliding SYMBOL '{rn}' on OsApplication '{app}' between SWCs: "
                + ", ".join(other_swcs)
                + f". Rename SYMBOL in one SWC, OR map one SWC off OsApplication '{app}'."
            ]
            for p in party_list:
                self.vlog(
                    self.validation_code, self.validation_summary,
                    msg, p["param_path"], "fail", [], solve,
                )
