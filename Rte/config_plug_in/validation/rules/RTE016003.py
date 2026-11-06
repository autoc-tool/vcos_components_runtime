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
"""RTE016003: missing DATA-READ/WRITE-ACCESS on mapped Application runnables.

Catches incomplete RTE configs where generate still succeeds but emits empty
Rte_IRead/IWrite (or skips com_exchange) because the runnable never claimed
access to COM-mapped / assembly-connected S/R data elements.
"""
from func_module.validation.common.basic_rule import BasicRule, timing_decorator
from basic_func_module.autosar_utils.utils import get_short_name
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


class Rte016003Rule(BasicRule):
    ruleset_name = "RTE016003"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = (
            "RTE016003: Application SWC runnables that are mapped to an OsTask must declare "
            "DATA-READ-ACCESSS / DATA-WRITE-ACCESSS (or explicit DATA-RECEIVE/SEND points) for "
            "every S/R data element that is system-signal data-mapped (COM) or assembly-connected. "
            "Otherwise Rte generate may succeed but produce empty Rte_I* APIs and no com_exchange."
        )
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.system_autosar_dict = validation_data.autosar_system_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict

    def check_validation_run(self):
        if not self.modules_are_exist(["Rte", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        if not self.asw_autosar_dict:
            return False
        return True

    @staticmethod
    def _ref_tail(ref) -> str:
        if ref is None:
            return ""
        val = getattr(ref, "valueOf_", None)
        if val is None:
            val = str(ref)
        return val.rstrip("/").split("/")[-1]

    @staticmethod
    def _ref_value(ref) -> str:
        if ref is None:
            return ""
        return getattr(ref, "valueOf_", None) or str(ref)

    def _collect_required_sr_elements(self):
        """Return set of (swc_type_name, port_name, de_name, direction) that need access.

        direction: 'W' for provider/P-port, 'R' for requester/R-port.
        """
        required = set()
        system = self.system_autosar_dict or {}
        flat = system.get("FlatExtract") if isinstance(system, dict) else None
        if flat is None:
            # system class may itself be the FlatExtract root
            flat = system

        roots = []
        if flat is not None:
            roots.append(flat)
        if self.asw_autosar_dict is not None:
            roots.append(self.asw_autosar_dict)

        # Assembly connectors: both ends need access on some mapped runnable of that SWC type
        for root in roots:
            try:
                connectors = root.find_nodes("ASSEMBLY-SW-CONNECTOR") or []
            except Exception:
                connectors = []
            for conn in connectors:
                try:
                    prov = conn.PROVIDER_IREF
                    req = conn.REQUESTER_IREF
                except AttributeError:
                    continue
                if not prov or not req:
                    continue
                p_swc = self._ref_tail(getattr(prov, "CONTEXT_COMPONENT_REF", None))
                r_swc = self._ref_tail(getattr(req, "CONTEXT_COMPONENT_REF", None))
                p_port = self._ref_tail(getattr(prov, "TARGET_P_PORT_REF", None))
                r_port = self._ref_tail(getattr(req, "TARGET_R_PORT_REF", None))
                # Resolve SWC type names from prototypes when possible; fall back to prototype short name
                # Data elements filled later from SWC type ports.
                if p_swc and p_port:
                    required.add((p_swc, p_port, "*", "W"))
                if r_swc and r_port:
                    required.add((r_swc, r_port, "*", "R"))

        # System-signal / COM data mappings (DATA-MAPPING under FlatExtract SYSTEM)
        for root in roots:
            try:
                mappings = root.find_nodes("DATA-MAPPING") or []
            except Exception:
                mappings = []
            # Some ARXML use SYSTEM-MAPPING / SW-IMPL-MAPPING; also look for I-SIGNAL-TO-* patterns
            try:
                mappings += root.find_nodes("SENDER-RECEIVER-TO-SIGNAL-MAPPING") or []
            except Exception:
                pass
            try:
                mappings += root.find_nodes("SENDER-RECEIVER-TO-SIGNAL-GROUP-MAPPING") or []
            except Exception:
                pass
            for m in mappings:
                # DATA-ELEMENT-IREF / SENDER-RECEIVER-TO-SIGNAL* styles
                irefs = []
                de_iref = getattr(m, "DATA_ELEMENT_IREF", None) or getattr(m, "CONTEXT_DATA_ELEMENT_IREF", None)
                if de_iref is not None:
                    irefs = [de_iref]
                elif hasattr(m, "DATA_ELEMENT_IREFS") and m.DATA_ELEMENT_IREFS is not None:
                    irefs = getattr(m.DATA_ELEMENT_IREFS, "DATA_ELEMENT_IREF", None) or []
                    if not isinstance(irefs, list):
                        irefs = [irefs] if irefs else []
                # Some mappings expose PORT/DE refs directly on the mapping node
                if not irefs:
                    port_ref = getattr(m, "CONTEXT_PORT_REF", None)
                    de_ref = getattr(m, "TARGET_DATA_PROTOTYPE_REF", None) or getattr(
                        m, "DATA_ELEMENT_REF", None
                    )
                    comp_ref = getattr(m, "CONTEXT_COMPONENT_REF", None)
                    if port_ref is not None or de_ref is not None:
                        class _Fake:
                            pass
                        fake = _Fake()
                        fake.CONTEXT_PORT_REF = port_ref
                        fake.TARGET_DATA_PROTOTYPE_REF = de_ref
                        fake.CONTEXT_COMPONENT_REF = comp_ref
                        irefs = [fake]
                for iref in irefs:
                    if iref is None:
                        continue
                    ctx = getattr(iref, "CONTEXT_COMPONENT_REF", None) or getattr(
                        iref, "CONTEXT_PORT_REF", None
                    )
                    # Prefer CONTEXT-PORT-REF + TARGET-DATA-PROTOTYPE-REF pattern
                    port_ref = getattr(iref, "CONTEXT_PORT_REF", None)
                    de_ref = getattr(iref, "TARGET_DATA_PROTOTYPE_REF", None) or getattr(
                        iref, "TARGET_DATA_ELEMENT_REF", None
                    )
                    comp_ref = getattr(iref, "CONTEXT_COMPONENT_REF", None)
                    swc = self._ref_tail(comp_ref) if comp_ref else ""
                    port = self._ref_tail(port_ref) if port_ref else self._ref_tail(ctx)
                    de = self._ref_tail(de_ref) if de_ref else "*"
                    # Direction: P-PORT vs R-PORT from DEST if present
                    direction = "W"
                    port_dest = ""
                    if port_ref is not None:
                        port_dest = getattr(port_ref, "DEST", None) or ""
                    if "R-PORT" in str(port_dest).upper():
                        direction = "R"
                    elif "P-PORT" in str(port_dest).upper():
                        direction = "W"
                    if swc and port:
                        required.add((swc, port, de, direction))

        return required

    def _swc_port_data_elements(self, swc):
        """Yield (port_name, de_name, direction) for S/R ports on an Application SWC type."""
        out = []
        ports_container = getattr(swc, "PORTS", None)
        if not ports_container:
            return out
        for tag, direction in (
            ("P_PORT_PROTOTYPE", "W"),
            ("R_PORT_PROTOTYPE", "R"),
        ):
            plist = getattr(ports_container, tag, None) or []
            if not isinstance(plist, list):
                plist = [plist]
            for port in plist:
                if port is None:
                    continue
                port_name = get_short_name(port)
                # provided / required interface must be S/R
                iface_ref = getattr(port, "PROVIDED_INTERFACE_TREF", None) or getattr(
                    port, "REQUIRED_INTERFACE_TREF", None
                )
                # data elements via PROVIDED-COM-SPECS / REQUIRED-COM-SPECS
                specs = None
                if direction == "W":
                    specs = getattr(port, "PROVIDED_COM_SPECS", None)
                else:
                    specs = getattr(port, "REQUIRED_COM_SPECS", None)
                des = []
                if specs is not None:
                    for spec_tag in (
                        "NONQUEUED_SENDER_COM_SPEC",
                        "QUEUED_SENDER_COM_SPEC",
                        "NONQUEUED_RECEIVER_COM_SPEC",
                        "QUEUED_RECEIVER_COM_SPEC",
                    ):
                        items = getattr(specs, spec_tag, None) or []
                        if not isinstance(items, list):
                            items = [items]
                        for item in items:
                            if item is None:
                                continue
                            de_ref = getattr(item, "DATA_ELEMENT_REF", None)
                            de_name = self._ref_tail(de_ref)
                            if de_name:
                                des.append(de_name)
                if not des:
                    # still record port-level wildcard so connector '*' matches
                    des = ["*"]
                for de in des:
                    out.append((port_name, de, direction))
        return out

    def _runnable_accesses(self, runnable):
        """Return set of (port_name, de_name, direction) claimed by the runnable."""
        accesses = set()

        def add_from(container, direction):
            if not container:
                return
            vas = getattr(container, "VARIABLE_ACCESS", None) or []
            if not isinstance(vas, list):
                vas = [vas]
            for va in vas:
                if va is None:
                    continue
                ap = getattr(va, "ACCESSED_VARIABLE", None)
                if ap is None:
                    continue
                av = getattr(ap, "AUTOSAR_VARIABLE_IREF", None) or getattr(ap, "AUTOSAR_VARIABLE_IN_IMPL_DATATYPE", None)
                if av is None:
                    # some schemas nest differently
                    av = ap
                port_ref = getattr(av, "PORT_PROTOTYPE_REF", None)
                de_ref = getattr(av, "TARGET_DATA_PROTOTYPE_REF", None)
                port = self._ref_tail(port_ref)
                de = self._ref_tail(de_ref)
                if port and de:
                    accesses.add((port, de, direction))
                    accesses.add((port, "*", direction))

        add_from(getattr(runnable, "DATA_WRITE_ACCESSS", None), "W")
        add_from(getattr(runnable, "DATA_SEND_POINTS", None), "W")
        add_from(getattr(runnable, "DATA_READ_ACCESSS", None), "R")
        add_from(getattr(runnable, "DATA_RECEIVE_POINT_BY_ARGUMENTS", None), "R")
        add_from(getattr(runnable, "DATA_RECEIVE_POINT_BY_VALUES", None), "R")
        return accesses

    def _mapped_runnable_paths(self):
        """Return dict swc_type_name -> set of runnable short names that are task-mapped."""
        mapped = {}
        rte = self.bsw_ecuc_cfg_class_dict.get("Rte")
        if not rte:
            return mapped
        try:
            rte_root = rte["ArPackages"]["ActiveEcuC"]["Rte"]
        except Exception:
            return mapped
        asw = self.asw_autosar_dict
        for _k, inst in rte_root.items():
            if not isinstance(inst, dict):
                continue
            if "RteSwComponentInstance" not in str(inst.get("DefinitionRef", "")):
                continue
            # Walk event mappings
            for _sk, sub in inst.items():
                if not isinstance(sub, dict):
                    continue
                if "RteEventToTaskMapping" not in str(sub.get("DefinitionRef", "")):
                    continue
                event_ref = None
                task_ref = None
                for _pk, pv in sub.items():
                    if not isinstance(pv, dict):
                        continue
                    dref = str(pv.get("DefinitionRef", ""))
                    if dref.endswith("RteEventRef"):
                        event_ref = pv.get("ValueRef")
                    if dref.endswith("RteMappedToTaskRef"):
                        task_ref = pv.get("ValueRef")
                if not event_ref or not task_ref:
                    continue
                # Resolve runnable via ASW event START-ON-EVENT-REF
                try:
                    event = asw.find(event_ref) if asw else None
                except Exception:
                    event = None
                if not event:
                    continue
                start_ref = getattr(getattr(event, "START_ON_EVENT_REF", None), "valueOf_", None)
                if not start_ref:
                    continue
                try:
                    runnable = asw.find(start_ref)
                except Exception:
                    runnable = None
                if not runnable:
                    continue
                # SWC type = parent path ComponentTypes/<Swc>/...
                parts = start_ref.strip("/").split("/")
                # expect ComponentTypes / SwcName / ...
                swc_name = parts[1] if len(parts) > 1 and parts[0] in ("ComponentTypes", "Components") else parts[0]
                rname = get_short_name(runnable)
                mapped.setdefault(swc_name, set()).add(rname)
        return mapped

    def _expand_required_with_port_des(self, required, swc_ports):
        """Expand (swc, port, '*', dir) using concrete DEs from swc_ports dict."""
        expanded = set()
        for swc, port, de, direction in required:
            if de != "*":
                expanded.add((swc, port, de, direction))
                continue
            for p, d, direc in swc_ports.get(swc, []):
                if p == port and direc == direction:
                    expanded.add((swc, port, d, direction))
            # keep wildcard if no concrete DE found (still flag missing any access on port)
            if not any(p == port and direc == direction for p, d, direc in swc_ports.get(swc, [])):
                expanded.add((swc, port, "*", direction))
        return expanded

    @timing_decorator
    def validation_run(self):
        asw = self.asw_autosar_dict
        swcs = []
        try:
            swcs = list(asw.find_nodes("APPLICATION-SW-COMPONENT-TYPE") or [])
            swcs += list(asw.find_nodes("ECU-ABSTRACTION-SW-COMPONENT-TYPE") or [])
        except Exception:
            swcs = []

        swc_by_name = {get_short_name(s): s for s in swcs if s is not None}
        swc_ports = {name: self._swc_port_data_elements(swc) for name, swc in swc_by_name.items()}

        required_raw = self._collect_required_sr_elements()
        # Prototype short names in connectors may equal type names (ms9/ms13: MinimalSystem / IoHwAb)
        required = self._expand_required_with_port_des(required_raw, swc_ports)

        mapped = self._mapped_runnable_paths()

        # Build access coverage per SWC from mapped runnables only
        coverage = {}  # swc -> set of (port, de, dir)
        runnable_paths = {}  # swc -> list of runnable paths for messaging
        for swc_name, swc in swc_by_name.items():
            coverage[swc_name] = set()
            runnable_paths[swc_name] = []
            ibs = getattr(swc, "INTERNAL_BEHAVIORS", None)
            if not ibs or not getattr(ibs, "SWC_INTERNAL_BEHAVIOR", None):
                continue
            behaviors = ibs.SWC_INTERNAL_BEHAVIOR
            if not isinstance(behaviors, list):
                behaviors = [behaviors]
            mapped_names = mapped.get(swc_name, set())
            for beh in behaviors:
                if not beh or not getattr(beh, "RUNNABLES", None):
                    continue
                runnables = beh.RUNNABLES.RUNNABLE_ENTITY or []
                if not isinstance(runnables, list):
                    runnables = [runnables]
                for runnable in runnables:
                    if runnable is None:
                        continue
                    rname = get_short_name(runnable)
                    if mapped_names and rname not in mapped_names:
                        # SWC has mappings: only count mapped runnables
                        continue
                    if not mapped_names:
                        # No task mapping at all for this SWC — skip (other rules cover unmapped)
                        continue
                    acc = self._runnable_accesses(runnable)
                    coverage[swc_name] |= acc
                    try:
                        runnable_paths[swc_name].append(runnable.get_path())
                    except Exception:
                        runnable_paths[swc_name].append(f"/ComponentTypes/{swc_name}/.../{rname}")

        # Evaluate required elements
        reported = set()
        any_fail = False
        for swc, port, de, direction in sorted(required):
            if swc not in swc_by_name:
                # connector used prototype name that matches type — already handled; else skip unknown
                continue
            if swc not in mapped or not mapped[swc]:
                continue  # not task-mapped; don't fail here
            key = (swc, port, de, direction)
            if key in reported:
                continue
            covered = (
                (port, de, direction) in coverage.get(swc, set())
                or (port, "*", direction) in coverage.get(swc, set())
                or (de == "*" and any(p == port and dirc == direction for p, _, dirc in coverage.get(swc, set())))
            )
            param_path = (
                runnable_paths[swc][0]
                if runnable_paths.get(swc)
                else f"/ComponentTypes/{swc}"
            )
            access_kind = "DATA-WRITE-ACCESSS (or DATA-SEND-POINT)" if direction == "W" else (
                "DATA-READ-ACCESSS (or DATA-RECEIVE-POINT)"
            )
            de_txt = de if de != "*" else "<all data elements>"
            if not covered:
                any_fail = True
                reported.add(key)
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    (
                        f"SWC '{swc}' port '{port}' data element '{de_txt}' "
                        f"({'P-Port/sender' if direction == 'W' else 'R-Port/receiver'}) is "
                        f"COM data-mapped or assembly-connected, and runnable(s) "
                        f"{sorted(mapped.get(swc, []))} are mapped to an OsTask, but none of "
                        f"those runnables declare {access_kind} for it. Rte generate can still "
                        f"succeed while emitting empty/unconnected Rte_I* and skipping com_exchange."
                    ),
                    param_path,
                    "fail",
                    [],
                    [
                        f"On the TimingEvent runnable of '{swc}' (e.g. "
                        f"{sorted(mapped.get(swc, []))}), add {access_kind} for "
                        f"port '{port}' / data element '{de_txt}'.",
                        "Then re-run vcos_verify and force-generate Rte; confirm Rte_IRead/IWrite "
                        "macros are real assignments (not empty / /* unconnected */) and that "
                        "COM-mapped signals appear as com_receive_signal/com_send_signal in the "
                        "task body.",
                    ],
                )
            else:
                reported.add(key)
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    f"SWC '{swc}' port '{port}/{de_txt}' has required data access on a mapped runnable.",
                    param_path,
                    "pass",
                )

        if not reported:
            # No required elements found — pass with informational message
            self.vlog(
                self.validation_code,
                self.validation_summary,
                "No COM-mapped / assembly-connected S/R data elements requiring access checks.",
                "/ActiveEcuC/Rte",
                "pass",
            )
        return not any_fail
