# This Python file uses the following encoding: utf-8
"""RTE016004 (RteSoftwareComponentInstanceRef must target a SwComponentPrototype of the instance's SWC type).

Integration test: runs Studio verify on the AutoC PC ``minimal_system_re`` project with THIS runtime checkout.
Each case runs after a plain ``load_project`` and after a sparse re-parse of the ECUC files (Studio's
``refresh`` mode: no EcucArxmlUpdater slot completion), which is how AutoC-written ECUC reaches the live model.

Dependencies (the module is skipped, with the reason, when either is absent):
  VCOS_STUDIO_CONFIGURATOR  vcos_studio ``configurator`` dir containing tests/rte_task_mapping/studio_runner.py and
                            fixtures/minimal_system_re (vcos_studio PR #2, which also resolves SW-COMPONENT-PROTOTYPE
                            refs in FlatExtract; without it the valid refs fail RTE000000).
  VCOS_STUDIO_IT_ROOT       vcos tree with components/autoc_mcal/configurator_plug_in and the other components
                            (communication, rt_framework, ...). Its components/runtime, if any, is replaced by
                            this checkout.
Run with Studio's Python 3.8 environment:
  VCOS_STUDIO_CONFIGURATOR=... VCOS_STUDIO_IT_ROOT=... python -m pytest tests/Rte
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

RUNTIME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STUDIO_DIR = os.environ.get("VCOS_STUDIO_CONFIGURATOR", "")
VCOS_ROOT = os.environ.get("VCOS_STUDIO_IT_ROOT", "")
STUDIO_TESTS = os.path.join(STUDIO_DIR, "tests", "rte_task_mapping")
RUNNER = os.path.join(STUDIO_TESTS, "studio_runner.py")
FIXTURE_DIR = os.path.join(STUDIO_TESTS, "fixtures", "minimal_system_re", "pc")
PLUGIN_REL = os.path.join("components", "autoc_mcal", "configurator_plug_in")

pytestmark = [
    pytest.mark.skipif(
        not (STUDIO_DIR and os.path.isfile(RUNNER) and os.path.isdir(FIXTURE_DIR)),
        reason="set VCOS_STUDIO_CONFIGURATOR to a vcos_studio configurator with PR #2 "
        "(tests/rte_task_mapping/studio_runner.py and fixtures/minimal_system_re)",
    ),
    pytest.mark.skipif(
        not (VCOS_ROOT and os.path.isdir(os.path.join(VCOS_ROOT, PLUGIN_REL))),
        reason="set VCOS_STUDIO_IT_ROOT to a vcos tree with components/autoc_mcal/configurator_plug_in",
    ),
]

PROJECT_FILE = "minimal_system_re.vcosproject"
RTE_ECUC = os.path.join("config", "bsw", "Rte", "Rte_ecuc.arxml")
FLAT_EXTRACT = os.path.join("config", "system", "FlatExtract.arxml")
COMPOSITION = "/COM/VCOS2/CFG/WORKFLOW/SYSDESC/SYNC/COMPOSITIONTYPE"
SYS_CYCLE = f"{COMPOSITION}/SysCycle"
ACT_CYCLE = f"{COMPOSITION}/ActCycle"
MS_REF = "/ActiveEcuC/Rte/MinimalSystem_EcuSwComposition/RteSoftwareComponentInstanceRef"
IO_REF = "/ActiveEcuC/Rte/IoHwAb_EcuSwComposition/RteSoftwareComponentInstanceRef"
MODES = ["plain", "refresh"]


def components_tree(tmp_path):
    components = tmp_path / "vcos" / "components"
    components.mkdir(parents=True)
    for name in os.listdir(os.path.join(VCOS_ROOT, "components")):
        if name != "runtime":
            os.symlink(os.path.join(VCOS_ROOT, "components", name), str(components / name))
    os.symlink(RUNTIME_DIR, str(components / "runtime"))
    return components


def make_project(tmp_path, edits=()):
    components = components_tree(tmp_path)
    project_dir = tmp_path / "pc"
    shutil.copytree(FIXTURE_DIR, str(project_dir))
    project_file = project_dir / PROJECT_FILE
    cfg = json.loads(project_file.read_text(encoding="utf-8"))
    paths = cfg["path"]
    paths["studio_path"] = STUDIO_DIR
    paths["mcal_path"] = str(components / "autoc_mcal")
    paths["system_path"] = str(components / "autoc_mcal" / "configurator_plug_in")
    for key in ("swc_template_path", "bswcallout_path", "application_path"):
        paths[key] = str(tmp_path / "apps" / key)
    project_file.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    for rel, edit in edits:
        path = project_dir / rel
        text = path.read_text(encoding="utf-8")
        edited = edit(text)
        assert edited != text, f"edit of {rel} did not apply; fixture changed?"
        path.write_text(edited, encoding="utf-8")
    return project_dir


def verify(project_dir, mode):
    args = [sys.executable, RUNNER, str(project_dir / PROJECT_FILE), mode, "EcuC,Os,Rte"]
    proc = subprocess.run(args, cwd=STUDIO_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    out = proc.stdout.decode("utf-8", "replace")
    summary = json.loads(out.strip().splitlines()[-1])
    assert summary["load"] is True, out[-3000:]
    assert summary["crash"] is None, summary["crash"]
    first = summary["verify"][0]
    return first["result"]["Rte"], first["errors"]


def rte016004(errors):
    return sorted((e for e in errors if e["code"] == "RTE016004"), key=lambda e: e["paths"])


def swap_prototypes(text):
    text = text.replace(f"{SYS_CYCLE}<", "@@SWAP@@<").replace(f"{ACT_CYCLE}<", f"{SYS_CYCLE}<")
    return text.replace("@@SWAP@@<", f"{ACT_CYCLE}<")


def remove_io_ref(text):
    start = text.index("<ECUC-REFERENCE-VALUE>", text.index("<SHORT-NAME>IoHwAb_EcuSwComposition</SHORT-NAME>"))
    end = text.index("</ECUC-REFERENCE-VALUE>", start) + len("</ECUC-REFERENCE-VALUE>")
    assert "RteSoftwareComponentInstanceRef" in text[start:end]
    return text[:start] + text[end:]


def empty_io_ref(text):
    return text.replace(f'<VALUE-REF DEST="SW-COMPONENT-PROTOTYPE">{ACT_CYCLE}</VALUE-REF>', "")


def untype_act_cycle(text):
    return re.sub(r"(<SHORT-NAME>ActCycle</SHORT-NAME>\s*)<TYPE-TREF [^>]*>[^<]*</TYPE-TREF>", r"\1", text)


@pytest.mark.parametrize("mode", MODES)
def test_valid_prototype_refs_pass(tmp_path, mode):
    rte_ok, errors = verify(make_project(tmp_path), mode)
    assert rte016004(errors) == []
    assert rte_ok is True, errors


@pytest.mark.parametrize("edit", [remove_io_ref, empty_io_ref])
@pytest.mark.parametrize("mode", MODES)
def test_absent_optional_ref_passes(tmp_path, mode, edit):
    rte_ok, errors = verify(make_project(tmp_path, [(RTE_ECUC, edit)]), mode)
    assert rte016004(errors) == []
    assert rte_ok is True, errors


@pytest.mark.parametrize("mode", MODES)
def test_swapped_prototype_types_fail_with_path_and_fix(tmp_path, mode):
    rte_ok, errors = verify(make_project(tmp_path, [(RTE_ECUC, swap_prototypes)]), mode)
    io, ms = rte016004(errors)
    assert rte_ok is False
    assert io["paths"] == [IO_REF] and ms["paths"] == [MS_REF]
    assert f"references {SYS_CYCLE}, a prototype of SWC type 'MinimalSystem'" in io["message"]
    assert f"references {ACT_CYCLE}, a prototype of SWC type 'IoHwAb'" in ms["message"]
    assert io["solve"] == [[], [f"Set {IO_REF} to {ACT_CYCLE}"]]
    assert ms["solve"] == [[], [f"Set {MS_REF} to {SYS_CYCLE}"]]


@pytest.mark.parametrize("mode", MODES)
def test_prototype_without_type_tref_fails_with_path_and_fix(tmp_path, mode):
    rte_ok, errors = verify(make_project(tmp_path, [(FLAT_EXTRACT, untype_act_cycle)]), mode)
    [failure] = rte016004(errors)
    assert rte_ok is False
    assert failure["paths"] == [IO_REF]
    assert f"references {ACT_CYCLE}, a prototype without TYPE-TREF" in failure["message"]
    fix = f"No SwComponentPrototype of type IoHwAb exists; remove {IO_REF} (it is optional)"
    assert failure["solve"] == [[], [fix]]
