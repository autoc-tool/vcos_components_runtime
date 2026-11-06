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


# 动态缺失校验：对于非Port相关event触发的Runnable来说，要求必须mapped到一个Task
class Rte012002Rule(BasicRule):
    ruleset_name = "RTE012002"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = ("RTE012002: Application runnable triggered by a non-port event (Timing/Init/Mode/Background/…) must be mapped to an OsTask via RteEventToTaskMapping.")
        self.rte_common_data = rte_common_data
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.root_item = rte_common_data.get_root_item()

        self.runnable_dict = RteUtils.get_runnable_dict(self.root_item)

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False

        return True

    def _event_refs_match(self, mapping_event_ref, runnable_event_ref) -> bool:
        """Match RteEventRef against runnable EventRef (str or list)."""
        if not mapping_event_ref:
            return False
        m = mapping_event_ref if isinstance(mapping_event_ref, str) else str(mapping_event_ref)
        m_short = m.split("/")[-1]
        refs = runnable_event_ref if isinstance(runnable_event_ref, (list, tuple)) else [runnable_event_ref]
        for r in refs:
            if not r:
                continue
            r_s = r if isinstance(r, str) else str(r)
            if r_s == m or r_s.split("/")[-1] == m_short or m.endswith(r_s) or r_s.endswith(m):
                return True
        return False

    def _is_mapped_in_ecuc(self, event_ref) -> bool:
        """True if RteEventToTaskMapping maps this event to a task.

        Task-mapping UI headers exclude OsTaskAutostart==TRUE (e.g. OsTask_Init), so
        runnables mapped only to those tasks stay mapped_status=False in the tree even
        though ECUC already has RteMappedToTaskRef. Treat such ECUC mappings as mapped.
        """
        try:
            rte_root = self.bsw_ecuc_cfg_class_dict["Rte"]["ArPackages"]["ActiveEcuC"]["Rte"]
        except (KeyError, TypeError, AttributeError):
            return False
        if not isinstance(rte_root, dict):
            return False
        for swc_inst in rte_root.values():
            if not isinstance(swc_inst, dict):
                continue
            for item in swc_inst.values():
                if not isinstance(item, dict):
                    continue
                defref = item.get("DefinitionRef") or ""
                if "RteEventToTaskMapping" not in str(defref):
                    continue
                mapped_task = (item.get("RteMappedToTaskRef") or {}).get("ValueRef")
                if not mapped_task:
                    continue
                ev = (item.get("RteEventRef") or {}).get("ValueRef")
                if self._event_refs_match(ev, event_ref):
                    return True
        return False

    @timing_decorator
    def validation_run(self):
        category_name_list = ['Application Components']

        for category_name, category_instance in self.runnable_dict.items():
            if category_name not in category_name_list:
                continue
            for swc_name, swc_instance in category_instance.items():
                for runnable_name, runnable_instance in swc_instance.items():
                    # 忽略被port相关event触发的runnable
                    if not runnable_instance['has_no_port_event']:
                        continue

                    mapped_status = runnable_instance['mapped_status']
                    param_path = runnable_instance['event_ref']
                    if not mapped_status and self._is_mapped_in_ecuc(param_path):
                        mapped_status = True
                    if not mapped_status:
                        rte_swc_path = f"/ActiveEcuC/Rte/{swc_name}"
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            (
                                f"Runnable '{runnable_name}' in SWC '{swc_name}' ({category_name}) "
                                f"has a non-port trigger event but is not mapped to any OsTask. "
                                f"Create/update RteEventToTaskMapping under {rte_swc_path}: "
                                f"set RteEventRef to the runnable's trigger event "
                                f"({param_path}) and RteMappedToTaskRef to an OsTask "
                                f"(prefer a non-autostart task so the mapping UI sees it)."
                            ),
                            param_path if param_path else rte_swc_path,
                            "fail",
                            [],
                            [
                                f"Map {swc_name}/{runnable_name} to an OsTask via "
                                f"Rte/{swc_name}/RteEventToTaskMapping "
                                f"(RteEventRef + RteMappedToTaskRef)."
                            ],
                        )
                    else:
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"swc={swc_name} runnable={runnable_name}: mapped.",
                            param_path, "pass")
