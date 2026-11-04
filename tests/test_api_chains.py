import shutil
from pathlib import Path

import pytest

from studio_hub.api import Api
from studio_hub.bridge import ReaperBridge
from studio_hub.library import Library
from studio_hub.reaper_db import Plugin
from tests.fake_reaper import FakeReaper

FIX = Path(__file__).parent / "fixtures" / "reaper"
EQ_AND_UNKNOWN = ('BYPASS 0 0 0\n<VST "VST: ReaComp (Cockos)" reacomp.dll 0 "" 1<56>\nAA==\n>\n'
                  'BYPASS 0 0 0\n<VST "VST3: Gone (Nobody)" gone.vst3 0 "" 2{3}\nAA==\n>\n'
                  'BYPASS 0 0 0\n<JS "utility/volume" ""\n>\n'
                  'BYPASS 0 0 0\n<VST "VST3: Comp (Mono) (Vendor)" c.vst3 0 "" 4{5}\nAA==\n>\n')


class StubCapture:
    def status(self): return {}


@pytest.fixture
def env(tmp_path):
    reaper_dir = tmp_path / "reaper"
    shutil.copytree(FIX, reaper_dir)
    (reaper_dir / "FXChains" / "Ordel").mkdir(parents=True)
    (reaper_dir / "FXChains" / "Mine").mkdir()
    (reaper_dir / "FXChains" / "Mine" / "Vocal.RfxChain").write_text(EQ_AND_UNKNOWN)
    (reaper_dir / "FXChains" / "Ordel" / "Plate.RfxChain").write_text(EQ_AND_UNKNOWN)
    fake = FakeReaper(tmp_path / "bridge")
    api = Api(reaper_dir, Library(tmp_path / "lib.json"), ReaperBridge(tmp_path / "bridge"), StubCapture(), {})
    main = Plugin("aaaaaaaaaaaa", "Comp", "Vendor", "VST3", False, "VST3: Comp (Vendor)")
    main.variants = [Plugin("bbbbbbbbbbbb", "Comp (Mono)", "Vendor", "VST3", False, "VST3: Comp (Mono) (Vendor)",
                            variant="Mono")]
    api.plugins.append(main)
    yield api, fake, reaper_dir
    fake.stop()


def chain(api, name):
    return next(c for c in api.state()["chains"] if c["name"] == name)


def test_lists_reaper_and_ordel_chains_with_matched_plugins(env):
    api, _, _ = env
    vocal, plate = chain(api, "Vocal"), chain(api, "Plate")
    assert vocal["kind"] == "file" and vocal["ordel"] is False and plate["ordel"] is True
    reacomp = next(p for p in api.plugins if p.name == "ReaComp")
    assert vocal["plugins"][0] == {"name": "ReaComp", "id": reacomp.id, "variant": reacomp.id}
    assert vocal["plugins"][1] == {"name": "Gone", "id": None, "variant": None}
    assert vocal["plugins"][3] == {"name": "Comp", "id": "aaaaaaaaaaaa", "variant": "bbbbbbbbbbbb"}
    assert vocal["return_track"] is False and vocal["hidden"] is False


def test_apply_reports_missing_plugins_but_not_reapers_own_effects(env):
    api, fake, reaper_dir = env
    fake.replies["CHAIN_APPLY"] = "OK\t2"
    r = api.chain_action("apply", id=chain(api, "Vocal")["id"])
    assert r == {"ok": True, "detail": "2", "missing": ["Gone"], "exists": False, "tracks": 2}
    path = reaper_dir / "FXChains" / "Mine" / "Vocal.RfxChain"
    assert fake.received[-1] == ("CHAIN_APPLY", f"track\tVocal\t{path}")


def test_return_chain_applies_as_a_return_track_and_reports_duplicates(env):
    api, fake, _ = env
    plate = chain(api, "Plate")["id"]
    api.chain_action("update", id=plate, return_track=True)
    fake.replies["CHAIN_APPLY"] = "OK\tEXISTS"
    r = api.chain_action("apply", id=plate)
    assert r["exists"] is True and r["ok"] and fake.received[-1][1].startswith("return\tPlate\t")


def test_save_goes_into_ordels_folder_and_lists_last(env):
    api, fake, reaper_dir = env
    r = api.chain_action("save", name='Lead: "vox"')
    assert fake.received[-1] == ("CHAIN_SAVE", str(reaper_dir / "FXChains" / "Ordel" / "Lead vox.RfxChain"))
    assert r["ok"] and r["id"] == "file:Ordel/Lead vox.RfxChain"
    (reaper_dir / "FXChains" / "Ordel" / "Lead vox.RfxChain").write_text(EQ_AND_UNKNOWN)  # what REAPER writes
    assert api.state()["chains"][-1]["name"] == "Lead vox"
    with pytest.raises(ValueError):
        api.chain_action("save", name="  ")


def test_built_chain_adds_the_chosen_versions(env):
    api, fake, _ = env
    reacomp = next(p for p in api.plugins if p.name == "ReaComp")
    r = api.chain_action("build", name="Drums", plugins=[reacomp.id, "bbbbbbbbbbbb"])
    built = chain(api, "Drums")
    assert built["id"] == r["id"] and built["kind"] == "built" and built["ordel"] is True
    assert [p["variant"] for p in built["plugins"]] == [reacomp.id, "bbbbbbbbbbbb"]
    api.chain_action("apply", id=r["id"])
    assert fake.received[-1] == ("CHAIN_ADD", "track\tDrums\tVST: ReaComp (Cockos)\tVST3: Comp (Mono) (Vendor)")
    with pytest.raises(ValueError):
        api.chain_action("build", name="X", plugins=["nope"])


def test_saving_over_a_built_chain_turns_it_into_a_file(env):
    api, fake, reaper_dir = env
    r = api.chain_action("build", name="Drums", plugins=["bbbbbbbbbbbb"])
    api.chain_action("update", id=r["id"], return_track=True)
    saved = api.chain_action("save", name="Drums", replace=r["id"])
    (reaper_dir / "FXChains" / "Ordel" / "Drums.RfxChain").write_text(EQ_AND_UNKNOWN)
    names = [c["name"] for c in api.state()["chains"]]
    assert names.count("Drums") == 1 and chain(api, "Drums")["id"] == saved["id"] == "file:Ordel/Drums.RfxChain"
    assert chain(api, "Drums")["return_track"] is True


def test_rename_moves_an_ordel_file_but_not_a_reaper_one(env):
    api, _, reaper_dir = env
    api.chain_action("update", id=chain(api, "Plate")["id"], name="Big Plate")
    assert (reaper_dir / "FXChains" / "Ordel" / "Big Plate.RfxChain").exists()
    assert chain(api, "Big Plate")["id"] == "file:Ordel/Big Plate.RfxChain"
    with pytest.raises(ValueError):
        api.chain_action("update", id=chain(api, "Vocal")["id"], name="Nope")


def test_move_hide_and_delete(env, monkeypatch):
    api, _, reaper_dir = env
    binned = []
    monkeypatch.setattr("studio_hub.chains.send_to_recycle_bin", lambda p: (binned.append(p), p.unlink()))
    first = api.state()["chains"][0]["name"]
    api.chain_action("move", id=api.state()["chains"][0]["id"], delta=1)
    assert api.state()["chains"][1]["name"] == first
    vocal = chain(api, "Vocal")["id"]
    api.chain_action("hide", id=vocal, hidden=True)
    assert chain(api, "Vocal")["hidden"] is True
    with pytest.raises(ValueError):
        api.chain_action("delete", id=vocal)  # made in REAPER: hide it instead
    api.chain_action("delete", id=chain(api, "Plate")["id"])
    assert binned == [reaper_dir / "FXChains" / "Ordel" / "Plate.RfxChain"]
    assert "Plate" not in [c["name"] for c in api.state()["chains"]]


def test_unknown_chain_or_action_is_rejected(env):
    api, _, _ = env
    with pytest.raises(ValueError):
        api.chain_action("apply", id="file:nope")
    with pytest.raises(ValueError):
        api.chain_action("explode", id=chain(api, "Vocal")["id"])


def test_replacing_an_ordel_chain_keeps_the_old_one_in_the_recycle_bin(env, monkeypatch):
    api, fake, reaper_dir = env
    binned = []
    monkeypatch.setattr("studio_hub.chains.send_to_recycle_bin",
                        lambda p: (binned.append((p.name, p.read_text())), p.unlink()))
    plate = reaper_dir / "FXChains" / "Ordel" / "Plate.RfxChain"
    api.chain_action("save", name="Plate", replace=chain(api, "Plate")["id"])
    assert binned == [("Plate (before replace).RfxChain", EQ_AND_UNKNOWN)]
    assert fake.received[-1] == ("CHAIN_SAVE", str(plate))
    assert "Plate (before replace)" not in [c["name"] for c in api.state()["chains"]]


def test_chain_settings_survive_the_chain_folder_going_missing(env):
    api, _, reaper_dir = env
    plate = chain(api, "Plate")["id"]
    api.chain_action("update", id=plate, return_track=True)
    shutil.move(str(reaper_dir / "FXChains"), str(reaper_dir / "FXChains-away"))
    api.state()  # e.g. a synced folder that is briefly unavailable
    shutil.move(str(reaper_dir / "FXChains-away"), str(reaper_dir / "FXChains"))
    assert chain(api, "Plate")["return_track"] is True


def test_js_effects_are_listed_by_name_not_file_path(env):
    api, _, _ = env
    assert chain(api, "Vocal")["plugins"][2] == {"name": "volume", "id": None, "variant": None}
