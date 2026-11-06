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
from durable import lang


# 互斥校验：检查EcuC的PDU不能只被1个模块reference。
class EcuC013001Rule(BasicRule):
    ruleset_name = "ECUC013001"

    def __init__(self, logs, bsw_ecuc_cfg_class_dict) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = bsw_ecuc_cfg_class_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "Global PDU reference incomplete."
        self.durable_init()

    def durable_init(self):
        # 注：固定名称的规则集只能初始化一次，否则会异常报错
        try:
            lang.get_host().get_ruleset(self.__class__.ruleset_name)
        except Exception:
            # print('get_ruleset() exception message: {0}'.format(e.args))
            with lang.ruleset(self.__class__.ruleset_name):

                @lang.when_all((+lang.m.pdu_name) & (+lang.m.modules) & ((lang.m.modules != 1)))
                def fact(c):
                    self.__class__.validation_result = True

            pass

    @timing_decorator
    def validation_run(self):
        ref_ecuc_dict = {}
        ref_ecuc_dict["CanIf"] = self._get_canif_ref_ecuc_pdu()
        ref_ecuc_dict["LinIf"] = self._get_linif_ref_ecuc_pdu()
        ref_ecuc_dict["PduR"] = self._get_pdur_ref_ecuc_pdu()
        ref_ecuc_dict["Com"] = self._get_com_ref_ecuc_pdu()
        ref_ecuc_dict["CanNm"] = self._get_cannm_ref_ecuc_pdu()
        ref_ecuc_dict["Dcm"] = self._get_dcm_ref_ecuc_pdu()
        ref_ecuc_dict["CanTp"] = self._get_cantp_ref_ecuc_pdu()
        ref_ecuc_dict["Xcp"] = self._get_xcp_ref_ecuc_pdu()
        ecuc_pdu_list = self._get_ecuc_pdu()
        for pdu_name in ecuc_pdu_list:
            validation_data = {"pdu_name": pdu_name, "modules": []}
            for module_name, ref_list in ref_ecuc_dict.items():
                if pdu_name not in ref_list:
                    continue
                validation_data["modules"].append(module_name)
            try:
                self.__class__.validation_result = False
                if len(validation_data["modules"]) != 1:
                    self.__class__.validation_result = True
                # post(self.__class__.ruleset_name, validation_data)
            except Exception:
                self.__class__.validation_result = False
                # print('post() exception message {0}'.format(e.args))
                pass

            # 格式："错误码", "摘要", "错误信息", "错误索引路径" "结果"
            if self.__class__.validation_result:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    "port_type:, signal_direction:",
                    f"/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection/{pdu_name}",
                    "pass",
                )
            else:
                self.vlog(
                    self.validation_code,
                    self.validation_summary,
                    f"{validation_data['modules']}",
                    f"/ActiveEcuC/EcuC/EcucConfigSet/EcucPduCollection/{pdu_name}",
                    "fail",
                )

    def _get_pdur_ref_ecuc_pdu(self):
        pdur_ref_ecuc = []
        pdur_cfg = self._get_value_by_keys(self.bsw_ecuc_cfg_class_dict, "PduR", "ArPackages", "ActiveEcuC", "PduR")
        if pdur_cfg is None:
            return
        pdur_routing_paths_dict = pdur_cfg.get("PduRRoutingPaths", {})
        for pdu_name, pdur_routing_path in pdur_routing_paths_dict.items():
            if not isinstance(pdur_routing_path, dict):
                continue
            if pdur_routing_path.get("DefinitionRef", "").split("/")[-1] == "PduRSrcPdu":
                ecuc_ref = pdur_routing_path.get("PduRSrcPduRef", {}).get("ValueRef", "").split("/")[-1]
                pdur_ref_ecuc.append(ecuc_ref)
            elif pdur_routing_path.get("DefinitionRef", "").split("/")[-1] == "PduRDestPdu":
                ecuc_ref = pdur_routing_path.get("PduRDestPduRef", {}).get("ValueRef", "").split("/")[-1]
                pdur_ref_ecuc.append(ecuc_ref)
        return pdur_ref_ecuc

    def _get_com_ref_ecuc_pdu(self):
        com_ref_ecuc = []
        com_config = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "Com", "ArPackages", "ActiveEcuC", "Com", "ComConfig"
        )
        if com_config is None:
            return

        for name, ipdu in com_config.items():
            if not isinstance(ipdu, dict):
                continue
            if ipdu.get("DefinitionRef", "").split("/")[-1] == "ComIPdu":
                ecuc_ref = ipdu.get("ComPduIdRef", {}).get("ValueRef", "").split("/")[-1]
                com_ref_ecuc.append(ecuc_ref)
        return com_ref_ecuc

    def _get_canif_ref_ecuc_pdu(self):
        canif_ref_ecuc = []
        canif_pdu_dict = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "CanIf", "ArPackages", "ActiveEcuC", "CanIf", "CanIfInitCfg"
        )
        if canif_pdu_dict is None:
            return

        for name, ipdu in canif_pdu_dict.items():
            if not isinstance(ipdu, dict):
                continue
            if ipdu.get("DefinitionRef", "").split("/")[-1] == "CanIfRxPduCfg":
                ecuc_ref = ipdu.get("CanIfRxPduRef", {}).get("ValueRef", "").split("/")[-1]
                canif_ref_ecuc.append(ecuc_ref)
            elif ipdu.get("DefinitionRef", "").split("/")[-1] == "CanIfTxPduCfg":
                ecuc_ref = ipdu.get("CanIfTxPduRef", {}).get("ValueRef", "").split("/")[-1]
                canif_ref_ecuc.append(ecuc_ref)
        return canif_ref_ecuc

    def _get_linif_ref_ecuc_pdu(self):
        linif_ref_ecuc = []
        linif_global_config = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "LinIf", "ArPackages", "ActiveEcuC", "LinIf", "LinIfGlobalConfig"
        )
        if linif_global_config is None:
            return linif_ref_ecuc

        for name, linifchannel in linif_global_config.items():
            if not isinstance(linifchannel, dict):
                continue
            if linifchannel.get("DefinitionRef", "").split("/")[-1] == "LinIfChannel":
                for linifframe in linifchannel.values():
                    if not isinstance(linifframe, dict):
                        continue
                    if linifframe.get("DefinitionRef", "").split("/")[-1] != "LinIfFrame":
                        continue
                    for lin_if_pdu_direction in linifframe.values():
                        if not isinstance(lin_if_pdu_direction, dict):
                            continue
                        if lin_if_pdu_direction.get("DefinitionRef", "").split("/")[-1] != "LinIfPduDirection":
                            continue
                        for pdu in lin_if_pdu_direction.values():
                            if not isinstance(pdu, dict):
                                continue
                            if pdu.get("DefinitionRef", "").split("/")[-1] == "LinIfRxPdu":
                                ecuc_ref = pdu.get("LinIfRxPduRef", {}).get("ValueRef", "").split("/")[-1]
                                linif_ref_ecuc.append(ecuc_ref)
                            elif pdu.get("DefinitionRef", "").split("/")[-1] == "LinIfTxPdu":
                                ecuc_ref = pdu.get("LinIfTxPduRef", {}).get("ValueRef", "").split("/")[-1]
                                linif_ref_ecuc.append(ecuc_ref)
        return linif_ref_ecuc

    def _get_cannm_ref_ecuc_pdu(self):
        cannm_ref_ecuc = []
        cannm_global_config = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "CanNm", "ArPackages", "ActiveEcuC", "CanNm", "CanNmGlobalConfig"
        )
        if cannm_global_config is None:
            return
        for name, nm_channel in cannm_global_config.items():
            if not isinstance(nm_channel, dict):
                continue
            if nm_channel.get("DefinitionRef", "").split("/")[-1] == "CanNmChannelConfig":
                for key, pdu in nm_channel.items():
                    if not isinstance(pdu, dict):
                        continue
                    if pdu.get("DefinitionRef", "").split("/")[-1] == "CanNmRxPdu":
                        ecuc_ref = pdu.get("CanNmRxPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cannm_ref_ecuc.append(ecuc_ref)
                    elif pdu.get("DefinitionRef", "").split("/")[-1] == "CanNmTxPdu":
                        ecuc_ref = pdu.get("CanNmTxPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cannm_ref_ecuc.append(ecuc_ref)
        return cannm_ref_ecuc

    def _get_dcm_ref_ecuc_pdu(self):
        cannm_ref_ecuc = []
        dcm_dsl_connection = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict,
            "Dcm",
            "ArPackages",
            "ActiveEcuC",
            "Dcm",
            "DcmConfigSet",
            "DcmDsl",
            "DcmDslProtocol",
            "DcmDslProtocolRow",
            "DcmDslConnection",
        )
        if dcm_dsl_connection is None:
            return
        for dcm_dsl_main_connection in dcm_dsl_connection.values():
            if not isinstance(dcm_dsl_main_connection, dict):
                continue
            if dcm_dsl_main_connection.get("DefinitionRef", "").split("/")[-1] != "DcmDslMainConnection":
                continue
            for pdu in dcm_dsl_main_connection.values():
                if not isinstance(pdu, dict):
                    continue
                if pdu.get("DefinitionRef", "").split("/")[-1] == "DcmDslProtocolRx":
                    ecuc_ref = pdu.get("DcmDslProtocolRxPduRef", {}).get("ValueRef", "").split("/")[-1]
                    cannm_ref_ecuc.append(ecuc_ref)
                elif pdu.get("DefinitionRef", "").split("/")[-1] == "DcmDslProtocolTx":
                    ecuc_ref = pdu.get("DcmDslProtocolTxPduRef", {}).get("ValueRef", "").split("/")[-1]
                    cannm_ref_ecuc.append(ecuc_ref)
        return cannm_ref_ecuc

    def _get_cantp_ref_ecuc_pdu(self):
        cantp_ref_ecuc = []
        cantp_channel = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "CanTp", "ArPackages", "ActiveEcuC", "CanTp", "CanTpConfig", "CanTpChannel"
        )
        if cantp_channel is None:
            return []
        for cantp_nsdu in cantp_channel.values():
            if not isinstance(cantp_nsdu, dict):
                continue
            if cantp_nsdu.get("DefinitionRef", "").split("/")[-1] == "CanTpRxNSdu":
                ecuc_ref = cantp_nsdu.get("CanTpRxNSduRef", {}).get("ValueRef", "").split("/")[-1]
                cantp_ref_ecuc.append(ecuc_ref)
                for cantp_npdu in cantp_nsdu.values():
                    if not isinstance(cantp_npdu, dict):
                        continue
                    if cantp_npdu.get("DefinitionRef", "").split("/")[-1] == "CanTpRxNPdu":
                        ecuc_ref = cantp_npdu.get("CanTpRxNPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cantp_ref_ecuc.append(ecuc_ref)
                    elif cantp_npdu.get("DefinitionRef", "").split("/")[-1] == "CanTpTxFcNPdu":
                        ecuc_ref = cantp_npdu.get("CanTpTxFcNPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cantp_ref_ecuc.append(ecuc_ref)
            elif cantp_nsdu.get("DefinitionRef", "").split("/")[-1] == "CanTpTxNSdu":
                ecuc_ref = cantp_nsdu.get("CanTpTxNSduRef", {}).get("ValueRef", "").split("/")[-1]
                cantp_ref_ecuc.append(ecuc_ref)
                for cantp_npdu in cantp_nsdu.values():
                    if not isinstance(cantp_npdu, dict):
                        continue
                    if cantp_npdu.get("DefinitionRef", "").split("/")[-1] == "CanTpTxNPdu":
                        ecuc_ref = cantp_npdu.get("CanTpTxNPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cantp_ref_ecuc.append(ecuc_ref)
                    elif cantp_npdu.get("DefinitionRef", "").split("/")[-1] == "CanTpRxFcNPdu":
                        ecuc_ref = cantp_npdu.get("CanTpRxFcNPduRef", {}).get("ValueRef", "").split("/")[-1]
                        cantp_ref_ecuc.append(ecuc_ref)
        return cantp_ref_ecuc

    def _get_xcp_ref_ecuc_pdu(self):
        xcp_ref_ecuc = []
        xcp_config = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict, "Xcp", "ArPackages", "ActiveEcuC", "Xcp", "XcpConfig"
        )
        if xcp_config is None:
            return
        for xcp_pdu in xcp_config.values():
            if not isinstance(xcp_pdu, dict):
                continue
            if xcp_pdu.get("DefinitionRef", "").split("/")[-1] != "XcpPdu":
                continue
            for xcp_rx_tx_pdu in xcp_pdu.values():
                if not isinstance(xcp_rx_tx_pdu, dict):
                    continue
            if xcp_rx_tx_pdu.get("DefinitionRef", "").split("/")[-1] == "XcpRxPdu":
                ecuc_ref = xcp_rx_tx_pdu.get("XcpRxPduRef", {}).get("ValueRef", "").split("/")[-1]
                xcp_ref_ecuc.append(ecuc_ref)
            elif xcp_rx_tx_pdu.get("DefinitionRef", "").split("/")[-1] == "XcpTxPdu":
                ecuc_ref = xcp_rx_tx_pdu.get("XcpTxPduRef", {}).get("ValueRef", "").split("/")[-1]
                xcp_ref_ecuc.append(ecuc_ref)
        return xcp_ref_ecuc

    def _get_ecuc_pdu(self):
        cannm_ref_ecuc = []
        ecuc_pdu_collection = self._get_value_by_keys(
            self.bsw_ecuc_cfg_class_dict,
            "EcuC",
            "ArPackages",
            "ActiveEcuC",
            "EcuC",
            "EcucConfigSet",
            "EcucPduCollection",
        )
        if ecuc_pdu_collection is None:
            return
        for pdu_name, pdu in ecuc_pdu_collection.items():
            if not isinstance(pdu, dict):
                continue
            if pdu.get("DefinitionRef", "").split("/")[-1] != "Pdu":
                continue
            cannm_ref_ecuc.append(pdu_name)
        return cannm_ref_ecuc

    def _get_value_by_keys(self, cfg_dict, *args):
        rv = cfg_dict
        for arg in args:
            if not isinstance(rv, dict):
                return None
            rv = rv.get(arg, None)
        else:
            return rv
