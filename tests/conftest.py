import pytest
from pathlib import Path
import experiment_generator.experiment_generator as exp_gen
import experiment_generator.perturbation_experiment as pert_exp


class DummyBranch:
    def __init__(self, name):
        self.name = name


class DummyDiff:
    def __init__(self, a_path):
        self.a_path = a_path


class DummyIndex:
    def __init__(self, changed_files):
        self._changed_files = changed_files

    def diff(self, _):
        return (DummyDiff(file) for file in self._changed_files)


class DummyRepo:
    def __init__(self, branches=None, changed_files=None):
        if branches is None:
            branches = []
        if changed_files is None:
            changed_files = []

        self.branches = [DummyBranch(name) for name in branches]
        self.index = DummyIndex(changed_files)


class DummyGitRepository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.repo = DummyRepo()
        self.commits = []

    def commit(self, message, files):
        self.commits.append((message, files))

    def local_branches_dict(self):
        return {branch.name: branch for branch in self.repo.branches}


def dummy_clone(*args, **kwargs):
    return None


def dummy_checkout_branch(*args, **kwargs):
    return None


@pytest.fixture(autouse=True)
def patch_git(monkeypatch):
    """
    Auto-patch the clone, GitRepository and check_branch for testing.
    """

    # keep state consistent across tests
    gitrepo = DummyGitRepository(directory="dummy_repo")
    monkeypatch.setattr(pert_exp, "GitRepository", lambda directory: gitrepo)
    monkeypatch.setattr(exp_gen, "clone", dummy_clone)
    monkeypatch.setattr(pert_exp, "checkout_branch", dummy_checkout_branch)

    return gitrepo


# Recorder classes to capture the calls made to the experiment generator
class _RecorderBase:
    def __init__(self):
        self.calls = []

    def _record(self, method_name, params, filename):
        self.calls.append((method_name, params, filename))


class F90Recorder(_RecorderBase):
    def update_nml_params(self, params, filename, state=None, **kwargs):
        self._record("update_nml_params", params, filename)


class PayuconfigRecorder(_RecorderBase):
    def update_config_params(self, params, filename, state=None, **kwargs):
        self._record("update_config_params", params, filename)


class RunconfigRecorder(_RecorderBase):
    def update_runconfig_params(self, params, filename, state=None, **kwargs):
        self._record("update_runconfig_params", params, filename)


class Mom6Recorder(_RecorderBase):
    def update_mom6_params(self, params, filename, state=None, **kwargs):
        self._record("update_mom6_params", params, filename)


class RunseqRecorder(_RecorderBase):
    def update_nuopc_runseq(self, params, filename, state=None, **kwargs):
        self._record("update_nuopc_runseq", params, filename)


class Om2forcingRecorder(_RecorderBase):
    def update_forcing_params(self, params, filename, state=None, **kwargs):
        self._record("update_forcing_params", params, filename)


class FieldTableRecorder(_RecorderBase):
    def update_field_table_params(self, params, filename, state=None, **kwargs):
        self._record("update_field_table_params", params, filename)


@pytest.fixture(autouse=True)
def patch_updaters(monkeypatch):
    """
    Auto-patch the updater classes for testing.
    """
    f90_recorder = F90Recorder()
    payuconfig_recorder = PayuconfigRecorder()
    nuopc_runconfig_recorder = RunconfigRecorder()
    mom6_input_recorder = Mom6Recorder()
    nuopc_runseq_recorder = RunseqRecorder()
    om2_forcing_recorder = Om2forcingRecorder()
    field_table_recorder = FieldTableRecorder()

    monkeypatch.setattr(pert_exp, "F90NamelistUpdater", lambda *_: f90_recorder)
    monkeypatch.setattr(pert_exp, "ConfigUpdater", lambda *_: payuconfig_recorder)
    monkeypatch.setattr(pert_exp, "NuopcRunConfigUpdater", lambda *_: nuopc_runconfig_recorder)
    monkeypatch.setattr(pert_exp, "Mom6InputUpdater", lambda *_: mom6_input_recorder)
    monkeypatch.setattr(pert_exp, "NuopcRunseqUpdater", lambda *_: nuopc_runseq_recorder)
    monkeypatch.setattr(pert_exp, "Om2ForcingUpdater", lambda *_: om2_forcing_recorder)
    monkeypatch.setattr(pert_exp, "FieldTableUpdater", lambda *_: field_table_recorder)

    return (
        f90_recorder,
        payuconfig_recorder,
        nuopc_runconfig_recorder,
        mom6_input_recorder,
        nuopc_runseq_recorder,
        om2_forcing_recorder,
        field_table_recorder,
    )


@pytest.fixture
def tmp_repo_dir(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / "testing").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "config.yaml").write_text("""
queue: normal
ncpus: 240
jobfs: 10GB
mem: 960GB
walltime: 02:00:00
jobname: 100km_jra55do_ryf
model: access-om3
        """)
    (tmp_path / "input.nml").write_text("""
&MOM_input_nml
    output_directory = './'
    restart_input_dir = './'
    restart_output_dir = './'
    parameter_filename = 'MOM_input', 'MOM_override'
/
        """)
    (tmp_path / "ice_in").write_text("""
&setup_nml
  bfbflag = "off"
  conserv_check = .false.
  diagfreq = 960
  dumpfreq = "x"
  histfreq = "d", "m", "x", "x", "x"
/        """)
    (tmp_path / "nuopc.runseq").write_text("""
runSeq::
@3600
  MED med_phases_aofluxes_run
  MED med_phases_prep_ocn_accum
  MED med_phases_ocnalb_run
  MED med_phases_diag_ocn
@
::
    """)
    (tmp_path / "nuopc.runconfig").write_text("""
component_list: MED ATM ICE OCN ROF
ALLCOMP_attributes::
     ATM_model = datm
     GLC_model = sglc
     ICE_model = cice
::
        """)
    (tmp_path / "MOM_input").write_text("""
THICKNESSDIFFUSE_FIRST = True   !   [Boolean] default = False
                                ! If true, do thickness diffusion or interface height smoothing before dynamics.
                                ! This is only used if THICKNESSDIFFUSE or APPLY_INTERFACE_FILTER is true.
DT = 1800.0                     !   [s]
                                ! The (baroclinic) dynamics time step.  The time-step that is actually used will
                                ! be an integer fraction of the forcing time-step (DT_FORCING in ocean-only mode
                                ! or the coupling timestep in coupled mode.)
        """)
    (tmp_path / "atmosphere").mkdir(parents=True, exist_ok=True)
    (tmp_path / "atmosphere" / "forcing.json").write_text("""
{
  "description": "JRA55-do v1.4.0 IAF forcing",
  "inputs": [
    {
      "filename":
        "INPUT/tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-4-0_gr_{{year}}01010000-{{year}}12312100.nc",
      "fieldname": "tas",
      "cname": "tair_ai"
    },
    {
      "filename":
        "INPUT/uas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-4-0_gr_{{year}}01010000-{{year}}12312100.nc",
      "fieldname": "uas",
      "cname": "uwnd_ai"
    }
  ]
}
""")
    return tmp_path
