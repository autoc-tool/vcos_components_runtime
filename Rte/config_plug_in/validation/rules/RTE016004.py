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
from func_module.validation.common.validation_def import ValidationData
from basic_func_module.autosar_utils.utils import get_short_name, get_value_ref
from .Rte_common import RteCommonData

RTE_SWC_INSTANCE_SUFFIX = "_EcuSwComposition"


def _text(obj, attr):
    return getattr(getattr(obj, attr, None), "valueOf_", None) or ""


# RteSwComponentInstance "<SwcType>_EcuSwComposition" is the Rte configuration of SwcType (task mapping binds its
# runnables by that name). Its optional RteSoftwareComponentInstanceRef must therefore point at a
# SwComponentPrototype whose TYPE-TREF is SwcType. Unresolvable refs are reported by RTE000000.
class Rte016004Rule(BasicRule):
    ruleset_name = "RTE016004"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = (
            "RTE016004: RteSoftwareComponentInstanceRef of an RteSwComponentInstance must reference a "
            "SwComponentPrototype of the same SWC type."
        )
        self.rte_autosar = (validation_data.autosar_bsw_class or {}).get("Rte")
        self.search_objs = []
        if validation_data.autosar_asw_class:
            self.search_objs.append(validation_data.autosar_asw_class)
        flat_extract = (validation_data.autosar_system_class or {}).get("FlatExtract")
        if flat_extract:
            self.search_objs.append(flat_extract)

    def check_validation_run(self):
        return self.rte_autosar is not None and self.rte_autosar.find("/ActiveEcuC/Rte") is not None

    def find_prototype(self, path):
        for search_obj in self.search_objs:
            obj = search_obj.find(path)
            if obj is not None and obj.get_tag() == "SW-COMPONENT-PROTOTYPE":
                return obj
        return None

    def prototypes_of_type(self, swc_type):
        paths = []
        for search_obj in self.search_objs:
            for proto in search_obj.find_nodes("SW-COMPONENT-PROTOTYPE"):
                if _text(proto, "TYPE_TREF").split("/")[-1] == swc_type:
                    paths.append(proto.get_path())
        return sorted(set(paths))

    @timing_decorator
    def validation_run(self):
        rte_cfg = self.rte_autosar.find("/ActiveEcuC/Rte")
        containers = getattr(getattr(rte_cfg, "CONTAINERS", None), "ECUC_CONTAINER_VALUE", None) or []
        for container in containers:
            if not _text(container, "DEFINITION_REF").endswith("/RteSwComponentInstance"):
                continue
            instance_name = get_short_name(container)
            if not instance_name.endswith(RTE_SWC_INSTANCE_SUFFIX):
                continue
            swc_type = instance_name[: -len(RTE_SWC_INSTANCE_SUFFIX)]
            refs = getattr(getattr(container, "REFERENCE_VALUES", None), "ECUC_REFERENCE_VALUE", None) or []
            for ref in refs:
                if not _text(ref, "DEFINITION_REF").endswith("/RteSoftwareComponentInstanceRef"):
                    continue
                target = get_value_ref(ref)
                if not target:
                    continue
                param_path = f"/ActiveEcuC/Rte/{instance_name}/RteSoftwareComponentInstanceRef"
                proto = self.find_prototype(target)
                if proto is None:
                    continue
                proto_type = _text(proto, "TYPE_TREF").split("/")[-1]
                if proto_type == swc_type:
                    self.vlog(
                        self.validation_code,
                        self.validation_summary,
                        f"{param_path} -> {target} (type {proto_type})",
                        param_path,
                        "pass",
                    )
                    continue
                target_desc = (
                    f"a prototype of SWC type '{proto_type}'" if proto_type else "a prototype without TYPE-TREF"
                )
                candidates = self.prototypes_of_type(swc_type)
                fix = (
                    f"Set {param_path} to {' or '.join(candidates)}"
                    if candidates
                    else f"No SwComponentPrototype of type {swc_type} exists; remove {param_path} (it is optional)"
                )
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    (
                        f"{param_path} references {target}, {target_desc}, but "
                        f"{instance_name} configures SWC type '{swc_type}'. {fix}."
                    ),
                    param_path,
                    "fail",
                    [],
                    [fix],
                )
