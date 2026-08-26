from fatiguelife.cli import main


def test_run_command_prints_report_and_exports(tmp_path, capsys):
    rc = main(["run", "configs/baseline.yaml", "--outdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Illustrative Aluminium Alloy" in out
    assert "educational comparative model" in out
    assert "confidence" in out.lower()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.csv").exists()


def test_run_reports_warnings(tmp_path, capsys):
    main(["run", "configs/baseline.yaml", "--outdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert "WARNING" in out  # illustrative-data warning at minimum


def test_info_command(capsys):
    rc = main(["info", "configs/baseline.yaml"])
    out = capsys.readouterr().out
    assert rc == 0 and "Assumptions" in out


def test_invalid_config_is_friendly(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text('{"project": {"title": "x"}, "geometry": {"length_mm": 100}}')
    rc = main(["run", str(p), "--outdir", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 2 and "error:" in err and "Traceback" not in err


def test_sweep_and_optimize_commands(tmp_path, capsys):
    assert main(["sweep", "configs/baseline.yaml", "--outdir", str(tmp_path),
                 "--parameter", "alternating_load_n"]) == 0
    assert (tmp_path / "sweep_alternating_load_n.csv").exists()
    assert main(["optimize", "configs/optimization.yaml", "--outdir", str(tmp_path)]) == 0
    assert (tmp_path / "sizing.csv").exists()
    out = capsys.readouterr().out
    assert "not full shape optimization" in out


def test_sensitivity_command(capsys):
    assert main(["sensitivity", "configs/baseline.yaml"]) == 0
    assert "alternating_load_n" in capsys.readouterr().out
