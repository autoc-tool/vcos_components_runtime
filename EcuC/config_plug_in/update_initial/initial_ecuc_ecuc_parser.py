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
from basic_func_module.autosar_utils.autosar_util import AutosarUtil
from basic_func_module.autosar_utils.utils import get_definition_ref, set_value_ref, set_value, get_value


class InitialEcuCEcucParser:

    def __init__(self, mod_autosar_dict):
        self.mod_autosar_dict = mod_autosar_dict

    def __get_all_ecuc_core_defs(self, cfg_dict):
        ecuc_autosar = cfg_dict.get("ecuc_autosar", {}).get("EcuC", None)
        if not ecuc_autosar:
            return {}
        ret = {}
        ecuc_hws = ecuc_autosar.find("/ActiveEcuC/EcuC/EcucHardware")
        if not ecuc_hws:
            return {}
        for core_def in ecuc_hws.SUB_CONTAINERS.ECUC_CONTAINER_VALUE:
            for val in core_def.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE:
                if get_definition_ref(val).endswith("EcucCoreId"):
                    try:
                        ret[int(get_value(val))] = core_def.get_path()
                        break
                    except Exception:
                        continue
        return ret

    def update_initial_ecuc_from_dbc_ldf(self, initial_autosar, cfg_dict):
        core_defs = self.__get_all_ecuc_core_defs(cfg_dict)
        self.updata_ecuc_info_from_dbc_slot(initial_autosar, cfg_dict, core_defs)
        self.updata_ecuc_info_from_ldf_slot(initial_autosar, cfg_dict, core_defs)

    def updata_ecuc_info_from_dbc_slot(self, initial_autosar, dict, core_defs):
        self.ecuc_dbc_data = EcuCModuleData()
        if dict["dbc"] is not None:
            self.update_ecuc_arxml_from_add_dbc(initial_autosar, dict, core_defs)

    def updata_ecuc_info_from_ldf_slot(self, initial_autosar, dict, core_defs):
        self.ecuc_ldf_data = EcuCModuleData()
        if dict["ldf"] is not None:
            self.update_ecuc_arxml_from_add_ldf(initial_autosar, dict, core_defs)

    def update_ecuc_arxml_from_add_ldf(self, initial_autosar, cfg, core_defs):
        for ldf in cfg["ldf"]:
            core_id = ldf.get("coreId", None)
            core_ref = self.__update_core_def(cfg, core_defs, core_id)
            for msg_key, msg_value in ldf["details"].items():
                connect_list, msg_type = self._get_lin_pdu_connect_list(msg_key, msg_value, ldf["node_selected"])
                for connecter in connect_list:
                    if core_ref and "Dcm" in connecter:
                        l_core_ref = self.__update_core_def(cfg, core_defs, 0)
                        if msg_type == "dcm":
                            for slave_name in ldf["slaves_name"]:
                                pdu_info = self.ecuc_ldf_data.add_pdu_to_autosar_dict(
                                    f"{slave_name}_{msg_key}_o{connecter}", msg_value, l_core_ref
                                )
                                self._add_ecuc_pdu_to_arxml(initial_autosar, pdu_info)
                        else:
                            pdu_info = self.ecuc_ldf_data.add_pdu_to_autosar_dict(
                                f"{msg_key}_o{connecter}", msg_value, l_core_ref
                            )
                            self._add_ecuc_pdu_to_arxml(initial_autosar, pdu_info)
                    else:
                        if msg_type == "dcm":
                            for slave_name in ldf["slaves_name"]:
                                pdu_info = self.ecuc_ldf_data.add_pdu_to_autosar_dict(
                                    f"{slave_name}_{msg_key}_o{connecter}", msg_value, core_ref
                                )
                                self._add_ecuc_pdu_to_arxml(initial_autosar, pdu_info)
                        else:
                            pdu_info = self.ecuc_ldf_data.add_pdu_to_autosar_dict(
                                f"{msg_key}_o{connecter}", msg_value, core_ref
                            )
                            self._add_ecuc_pdu_to_arxml(initial_autosar, pdu_info)

    def update_ecuc_arxml_from_add_dbc(self, initial_autosar, cfg, core_defs):
        for dbc in cfg["dbc"]:
            core_id = dbc.get("coreId", None)
            core_ref = self.__update_core_def(cfg, core_defs, core_id)
            for msg_key, msg_value in dbc["details"].items():
                connect_list = self._get_can_pdu_connect_list(msg_key, msg_value, dbc["node_selected"])
                for connecter in connect_list:
                    if core_ref and "Dcm" in connecter:
                        l_core_ref = self.__update_core_def(cfg, core_defs, 0)
                        pdu_info = self.ecuc_dbc_data.add_pdu_to_autosar_dict(
                            f"{msg_key}_o{connecter}", msg_value, l_core_ref
                        )
                    else:
                        pdu_info = self.ecuc_dbc_data.add_pdu_to_autosar_dict(
                            f"{msg_key}_o{connecter}", msg_value, core_ref
                        )
                    self._add_ecuc_pdu_to_arxml(initial_autosar, pdu_info)

    def __update_core_def(self, cfg, core_defs, core_id):
        if core_id is None:
            return None
        if core_id not in core_defs:
            core_name = f"EcucCoreDefinition{core_id}"
            core_ref = f"/ActiveEcuC/EcuC/EcucHardware/{core_name}"
            core_defs[core_id] = core_ref
            if core_id != 0:
                ecuc_autosar = cfg.get("ecuc_autosar", {}).get("EcuC", None)
                if not ecuc_autosar:
                    return core_ref
                ecuc_hw = ecuc_autosar.find("/ActiveEcuC/EcuC/EcucHardware")
                self._creat_ecuc_sub_container(
                    ecuc_hw,
                    core_name,
                    "EcucCoreDefinition",
                    {
                        "Tag": "ECUC-CONTAINER-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition",
                        "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreId": {
                            "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                            "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreId",
                            "Value": core_id,
                        },
                        "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreHwRef": {
                            "Tag": "ECUC-REFERENCE-VALUE",
                            "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreHwRef",
                            "Value": "",
                        },
                    },
                )
        else:
            core_ref = core_defs[core_id]
        return core_ref

    def _get_can_pdu_connect_list(self, msg_key, msg_value, node_select):
        connect_list = []
        connect_dict = {
            "com": {
                "tx": ["Com_PduR_Tx", "PduR_CanIf_Tx"],
                "rx": ["CanIf_PduR_Rx", "PduR_Com_Rx"],
            },
            "cannm": {"tx": ["Com_CanNm_Tx", "CanNm_CanIf_Tx"], "rx": ["CanIf_CanNm_Rx", "CanNm_Com_Rx"]},
            "dcm": {
                "tx": ["Dcm_PduR_Tx", "PduR_CanTp_Tx", "CanTp_CanIf_Tx"],
                "rx": ["CanIf_CanTp_Rx", "CanTp_PduR_Rx", "PduR_Dcm_Rx"],
            },
            "xcp": {"tx": ["Xcp_CanIf_Tx"], "rx": ["CanIf_Xcp_Rx"]},
            "cantsyn": {"tx": ["CanTSyn_CanIf_Tx"], "rx": ["CanIf_CanTSyn_Rx"]},
            "others": {"tx": ["PduR_CanIf_Tx"], "rx": ["CanIf_PduR_Rx"]},
        }
        if (
            ("DiagRequest" in msg_value.message_attributes and msg_value.message_attributes["DiagRequest"].value == 1)
            or (
                "DiagResponse" in msg_value.message_attributes
                and msg_value.message_attributes["DiagResponse"].value == 1
            )
            or ("DiagState" in msg_value.message_attributes and msg_value.message_attributes["DiagState"].value == 1)
        ):
            module = "dcm"
        elif "NmAsrMessage" in msg_value.message_attributes and msg_value.message_attributes["NmAsrMessage"].value == 1:
            module = "cannm"
        elif (
            "GenMsgILSupport" in msg_value.message_attributes
            and msg_value.message_attributes["GenMsgILSupport"].value == 1
        ):
            module = "com"
        elif "XCP" in msg_key or "CCP" in msg_key:
            module = "xcp"
        elif "SYNCTime" in msg_key:
            module = "cantsyn"
        else:
            module = "others"

        if msg_value.senders[0] == node_select:
            dir = "tx"
        else:
            dir = "rx"

        if module is not None:
            connect_list = connect_dict[module][dir]
        return connect_list

    def _get_lin_pdu_connect_list(self, msg_key, msg_value, node_select):
        connect_list = []
        connect_dict = {
            "com": {
                "tx": ["Com_PduR_Tx", "PduR_LinIf_Tx"],
                "rx": ["LinIf_PduR_Rx", "PduR_Com_Rx"],
            },
            "dcm": {
                "tx": ["Dcm_PduR_Tx", "PduR_LinTp_Tx", "LinTp_LinIf_Tx"],
                "rx": ["LinIf_LinTp_Rx", "LinTp_PduR_Rx", "PduR_Dcm_Rx"],
            },
        }
        if msg_value.node_name == node_select:
            dir = "tx"
        else:
            dir = "rx"
        if msg_key.split(f"_o{msg_value.bus_name}")[0] == "MasterReq":
            module = "dcm"
            dir = "tx"
        elif msg_key.split(f"_o{msg_value.bus_name}")[0] == "SlaveResp":
            module = "dcm"
            dir = "rx"
        else:
            module = "com"
        if module is not None:
            connect_list = connect_dict[module][dir]
        return connect_list, module

    def _add_ecuc_pdu_to_arxml(self, initial_autosar, pdu_info):
        ecuc_autosar = initial_autosar.find("/InitialEcuC/EcuC")
        if ecuc_autosar is None:
            return
        parent = ecuc_autosar.find("/InitialEcuC/EcuC/EcucConfigSet/EcucPduCollection")
        for ecuc_pdu_name, ecuc_pdu_value in pdu_info.items():
            if ecuc_pdu_name in ["Tag", "DefinitionRef", "Description"] or not isinstance(ecuc_pdu_value, dict):
                continue
            self._creat_ecuc_sub_container(parent, ecuc_pdu_name, "Pdu", ecuc_pdu_value)

    def _creat_ecuc_sub_container(self, parent_container, container_name, container_mod_name, value_dict):
        created_container = None
        ecuc_def = self.mod_autosar_dict["EcuC"]
        parent_path = get_definition_ref(parent_container)
        # container_path = f"{parent_path}/{container_name}".replace("/AUTOSAR/EcucDefs","/ArPackages/ActiveEcuC")
        # key_list = [key for key in container_path.split("/") if key != ""]
        # had_container = _check_had_container(self.module_autosar_dict, key_list)
        # if had_container:
        #     return created_container
        if ecuc_def and parent_path and container_name and container_mod_name and isinstance(value_dict, dict):
            cur_conf_def = ecuc_def.find(parent_path + f"/{container_mod_name}")
            created_container = AutosarUtil.create_sub_container_value(container_name, cur_conf_def, parent_container)
            self._set_ecuc_container_obj_value_by_def_ref(created_container, value_dict)
        return created_container

    def _set_ecuc_container_obj_value_by_def_ref(self, container_obj, value_dict):
        ecuc_def = self.mod_autosar_dict["EcuC"]
        if not container_obj or not value_dict:
            return
        if container_obj.REFERENCE_VALUES and container_obj.REFERENCE_VALUES.ECUC_REFERENCE_VALUE:
            ref_num = len(container_obj.REFERENCE_VALUES.ECUC_REFERENCE_VALUE)
            for i in range(ref_num):
                para = container_obj.REFERENCE_VALUES.ECUC_REFERENCE_VALUE[i]
                def_ref = get_definition_ref(para)
                cur_conf_def = ecuc_def.find(def_ref)
                if def_ref not in value_dict.keys():
                    continue
                if isinstance(value_dict[def_ref]["Value"], list):
                    if len(value_dict[def_ref]["Value"]):
                        set_value_ref(para, str(value_dict[def_ref]["Value"][0]))
                        AutosarUtil.add_annotation_value(para, "AutoDerived")
                        for index in range(len(value_dict[def_ref]["Value"]) - 1):
                            obj = AutosarUtil.set_reference(container_obj.REFERENCE_VALUES, cur_conf_def)
                            set_value_ref(obj, str(value_dict[def_ref]["Value"][index + 1]))
                            AutosarUtil.add_annotation_value(obj, "AutoDerived")
                else:
                    set_value_ref(para, str(value_dict[def_ref]["Value"]))
                    AutosarUtil.add_annotation_value(para, "AutoDerived")
        if container_obj.PARAMETER_VALUES and container_obj.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE:
            for para in container_obj.PARAMETER_VALUES.ECUC_NUMERICAL_PARAM_VALUE:
                def_ref = get_definition_ref(para)
                if def_ref in value_dict.keys():
                    if value_dict.get(def_ref, {}).get("Value", None):
                        set_value(para, str(value_dict[def_ref]["Value"]))
                        AutosarUtil.add_annotation_value(para, "AutoDerived")
        if container_obj.PARAMETER_VALUES and container_obj.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE:
            for para in container_obj.PARAMETER_VALUES.ECUC_TEXTUAL_PARAM_VALUE:
                def_ref = get_definition_ref(para)
                if def_ref in value_dict.keys():
                    set_value(para, str(value_dict[def_ref]["Value"]))
                    AutosarUtil.add_annotation_value(para, "AutoDerived")


class EcuCModuleData:

    def __init__(self):
        self.data = {
            "EcucConfigSet": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet",
                "EcucPduCollection": {
                    "Tag": "ECUC-CONTAINER-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection",
                    "PduIdTypeEnum": {
                        "Tag": "ECUC-TEXTUAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/PduIdTypeEnum",
                        "Value": "",
                    },
                    "PduLengthTypeEnum": {
                        "Tag": "ECUC-TEXTUAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/PduLengthTypeEnum",
                        "Value": "",
                    },
                    "MetaDataType": {
                        "Tag": "ECUC-CONTAINER-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/MetaDataType",
                        "MetaDataItem": {
                            "Tag": "ECUC-CONTAINER-VALUE",
                            "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/MetaDataType/MetaDataItem",
                            "MetaDataItemLength": {
                                "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/MetaDataType/MetaDataItem/"
                                + "MetaDataItemLength",
                                "Value": 0,
                            },
                            "MetaDataItemType": {
                                "Tag": "ECUC-TEXTUAL-PARAM-VALUE",
                                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/MetaDataType/MetaDataItem/"
                                + "MetaDataItemType",
                                "Value": "",
                            },
                        },
                    },
                },
            },
            "EcucHardware": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware",
                "EcucCoreDefinition": {
                    "Tag": "ECUC-CONTAINER-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition",
                    "EcucCoreId": {
                        "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreId",
                        "Value": 0,
                    },
                    "EcucCoreHwRef": {
                        "Tag": "ECUC-REFERENCE-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition/EcucCoreHwRef",
                        "ValueRef": "",
                    },
                },
            },
            "EcucPartitionCollection": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection",
                "EcucPartition": {
                    "Tag": "ECUC-CONTAINER-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition",
                    "EcucPartitionBswModuleExecution": {
                        "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition/"
                        + "EcucPartitionBswModuleExecution",
                        "Value": "false",
                    },
                    "EcucPartitionQmBswModuleExecution": {
                        "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition/"
                        + "EcucPartitionQmBswModuleExecution",
                        "Value": "false",
                    },
                    "PartitionCanBeRestarted": {
                        "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition/PartitionCanBeRestarted",
                        "Value": "false",
                    },
                    "EcucPartitionBswModuleDistinguishedPartition": {
                        "Tag": "ECUC-REFERENCE-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition/"
                        + "EcucPartitionBswModuleDistinguishedPartition",
                        "ValueRef": "",
                    },
                    "EcucPartitionSoftwareComponentInstanceRef": {
                        "Tag": "ECUC-INSTANCE-REFERENCE-VALUE",
                        "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPartitionCollection/EcucPartition/"
                        + "EcucPartitionSoftwareComponentInstanceRef",
                        "ValueRef": "",
                    },
                },
            },
            "EcucPostBuildVariants": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPostBuildVariants",
                "EcucPostBuildVariantRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucPostBuildVariants/EcucPostBuildVariantRef",
                    "ValueRef": "",
                },
            },
            "EcucUnitGroupAssignment": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucUnitGroupAssignment",
                "EcucUnitGroupRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucUnitGroupAssignment/EcucUnitGroupRef",
                    "ValueRef": "",
                },
            },
            "EcucVariationResolver": {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucVariationResolver",
                "PredefinedVariantRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucVariationResolver/PredefinedVariantRef",
                    "ValueRef": "",
                },
            },
        }

    def add_pdu_to_autosar_dict(self, name, message_info, core_ref):
        if "Com_CanNm_Tx" in name or "CanNm_Com_Rx" in name:
            pdu_len = 6
        else:
            pdu_len = message_info.length
        pdu = {
            name: {
                "Tag": "ECUC-CONTAINER-VALUE",
                "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu",
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/PduLength": {
                    "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/PduLength",
                    "Value": pdu_len,
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/DynamicLength": {
                    "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/DynamicLength",
                    "Value": "false",
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/J1939Requestable": {
                    "Tag": "ECUC-NUMERICAL-PARAM-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/J1939Requestable",
                    "Value": "false",
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/MetaDataTypeRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/MetaDataTypeRef",
                    "Value": "",
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/SysTPduToFrameTriggeringRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/SysTPduToFrameTriggeringRef",
                    "Value": "",
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/SysTPduToPduTriggeringRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/SysTPduToPduTriggeringRef",
                    "Value": "",
                },
                "/AUTOSAR/EcucDefs/EcuC/EcucConfigSet/EcucPduCollection/Pdu/EcucPduDefaultCoreRef": {
                    "Tag": "ECUC-REFERENCE-VALUE",
                    "DefinitionRef": "/AUTOSAR/EcucDefs/EcuC/EcucHardware/EcucCoreDefinition",
                    "Value": core_ref if core_ref else "",
                },
            }
        }
        self.data["EcucConfigSet"]["EcucPduCollection"].update(pdu)
        return pdu


def _get_dict_value_by_nested_keys(target_dict, nested_key_list):
    rv = None
    find_value = target_dict
    if nested_key_list is None or len(nested_key_list) == 0:
        return rv
    for key in nested_key_list:
        if isinstance(find_value, dict) and key in find_value.keys():
            find_value = find_value[key]
        else:
            break
    else:
        rv = find_value
    return rv


def _check_had_container(target_dict, nested_key_list):
    rv = False
    find_value = target_dict
    if nested_key_list is None or len(nested_key_list) == 0:
        return rv
    for key in nested_key_list:
        if isinstance(find_value, dict) and key in find_value.keys():
            find_value = find_value[key]
        else:
            break
    else:
        rv = True
    return rv
