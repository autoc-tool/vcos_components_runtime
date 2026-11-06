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

from basic_func_module.autosar_utils.utils import get_short_name
from func_module.module_management.arxml_handler.ib_bswmd_process import ib_bswmd_utils
from func_module.generator.rte.rte_parser import get_rte_codegen_dict

# milli sec -> sec
MS_TO_S = 1000


def update_ib_bswmd(ib_autosar_dict, ecuc_autosar_dict, asw_autosar, autosar_system_dict, other_input_info):
    rte_ib = ib_autosar_dict.get("Rte", None)
    update_rte_com_send_signal_proxy_periodic(rte_ib, ecuc_autosar_dict, asw_autosar, autosar_system_dict, ib_autosar_dict, other_input_info)


def update_rte_com_send_signal_proxy_periodic(rte_ib, ecuc_autosar_dict, asw_autosar, autosar_system_dict, ib_autosar_dict, other_input_info):
    if (not rte_ib) or ("Rte" not in ecuc_autosar_dict) or ("Os" not in ecuc_autosar_dict) or \
            ("Com" not in ecuc_autosar_dict) or (not asw_autosar):
        __rmv_ib_arxml(rte_ib)
        return
    tx_proxies = __get_rte_com_proxy(asw_autosar, ecuc_autosar_dict, autosar_system_dict, ib_autosar_dict, other_input_info)
    __rmv_ib_arxml(rte_ib)
    if not tx_proxies:
        return

    for name, proxy in tx_proxies.items():
        postfix = proxy["postfix"]
        period_s = proxy["period"] / MS_TO_S
        ib_bswmd_utils.create_bsw_module_entry_ref_conditional(rte_ib, "Rte", name)

        timing_event_list = rte_ib.find_nodes("BSW-TIMING-EVENT")
        timing_evt_name = f"Rte_ComSendSignalProxyPeriodicTimingEvent{postfix}"
        for timing_event in timing_event_list:
            short_name = get_short_name(timing_event)
            if short_name == timing_evt_name:
                break
        else:
            ib_bswmd_utils.create_bsw_timing_event(rte_ib, "Rte", timing_evt_name,
                                                name, period_s)

        bsw_schedulable_entity_list = rte_ib.find_nodes("BSW-SCHEDULABLE-ENTITY")
        for bsw_schedulable_entity in bsw_schedulable_entity_list:
            short_name = get_short_name(bsw_schedulable_entity)
            if short_name == name:
                break
        else:
            ib_bswmd_utils.create_bsw_schedulable_entity(rte_ib, "Rte", name, name)

        bsw_module_entry_list = rte_ib.find_nodes("BSW-MODULE-ENTRY")
        for bsw_module_entry in bsw_module_entry_list:
            short_name = get_short_name(bsw_module_entry)
            if short_name == name:
                break
        else:
            ib_bswmd_utils.create_bsw_module_entry(rte_ib, "Rte", name)


def __rmv_ib_arxml(rte_ib):
    ib_bswmd_utils.delete_ib_container_with_prefix(rte_ib, "BSW-TIMING-EVENT", "Rte_ComSendSignalProxyPeriodicTimingEvent")
    ib_bswmd_utils.delete_ib_container_with_prefix(rte_ib, "BSW-SCHEDULABLE-ENTITY", "Rte_ComSendSignalProxyPeriodic")
    ib_bswmd_utils.delete_ib_container_with_prefix(rte_ib, "BSW-MODULE-ENTRY", "Rte_ComSendSignalProxyPeriodic")
    ib_bswmd_utils.delete_ib_node_with_prefix(rte_ib, "BSW-MODULE-ENTRY-REF-CONDITIONAL", "Rte_ComSendSignalProxyPeriodic")


def __get_rte_com_proxy(asw_autosar, ecuc_autosar_dict, system_autosar_dict, ib_autosar_dict, other_input_info):
    cfg_dict = {"asw": "", "rte": {}, "bsw": {}, "dbc": [], "ldf": [], "cdd": {}, "eb": {}}
    asw_dict = {"asw": asw_autosar, "FlatExtract": system_autosar_dict["FlatExtract"]}
    get_rte_codegen_dict(asw_dict, ecuc_autosar_dict, system_autosar_dict, ib_autosar_dict, cfg_dict, parse_new_dict=other_input_info.get("is_rte_parse_new_dict", True))
    if "data_mapping_config" not in cfg_dict["rte"]:
        return {}
    return cfg_dict["rte"]["data_mapping_config"]["signal_dict"]["tx_proxy"]
