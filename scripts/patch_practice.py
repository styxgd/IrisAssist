#!/usr/bin/env python3
"""Patch the MIT Frame Window Lab source for checkpoint-safe practice recording."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def change(file, before, after):
    p = ROOT / file
    contents = p.read_text(encoding="utf-8")
    if contents.count(before) != 1:
        raise RuntimeError(f"practice patch anchor mismatch in {file}: {before[:90]!r} ({contents.count(before)} hits)")
    p.write_text(contents.replace(before, after, 1), encoding="utf-8")

def main():
    change("src/Lab.hpp", "    void onResetAfter();\n",
        """    void onResetAfter();
    void onPracticeCheckpointStored(CheckpointObject* checkpoint);
    void onPracticeCheckpointsChanged();
""")
    change("src/Lab.hpp", "    std::set<std::pair<bool, int>> m_held;  // buttons held while recording\n",
        """    std::set<std::pair<bool, int>> m_held;  // buttons held while recording
    struct PracticeMark {
        CheckpointObject* checkpoint = nullptr; // identity only; never dereference
        int tick = 0;
        size_t inputCount = 0;
        std::set<std::pair<bool, int>> held;
    };
    bool m_practiceRecording = false;
    bool m_initialRecordingReset = false;
    bool m_practiceResume = false;
    int m_practiceResumeTick = 0;
    std::set<std::pair<bool, int>> m_practiceResumeHeld;
    std::vector<PracticeMark> m_practiceMarks;
""")
    change("src/Lab.cpp", "    m_held.clear();\n    reloadSettings();\n",
        """    m_held.clear();
    m_practiceRecording = false;
    m_initialRecordingReset = false;
    m_practiceResume = false;
    m_practiceMarks.clear();
    reloadSettings();
""")
    change("src/Lab.cpp", "    m_recording.reset();\n}\n\nvoid Lab::setMode",
        """    m_recording.reset();
    m_practiceMarks.clear();
    m_practiceRecording = false;
}

void Lab::setMode""")
    change("src/Lab.cpp", """    reloadSettings();
    if (m_layer->m_isPracticeMode) m_layer->togglePracticeMode(false);
    m_live = Recording{};
    m_live.levelKey = m_levelKey;
    m_live.levelName = std::string(m_layer->m_level->m_levelName);
    setMode(Mode::Recording);
    closePauseMenu();
    m_layer->resetLevelFromStart();
    return Ok();
}""", """    reloadSettings();
    // Recording stays in practice if the player selected it.
    m_practiceRecording = m_layer->m_isPracticeMode;
    m_practiceMarks.clear();
    m_practiceResume = false;
    m_live = Recording{};
    m_live.levelKey = m_levelKey;
    m_live.levelName = std::string(m_layer->m_level->m_levelName);
    setMode(Mode::Recording);
    closePauseMenu();
    m_initialRecordingReset = true;
    m_layer->resetLevelFromStart();
    m_initialRecordingReset = false;
    return Ok();
}""")
    change("src/Lab.cpp", """        case Mode::Recording:
            m_live = Recording{};
            setMode(Mode::Idle);
            break;""", """        case Mode::Recording:
            m_live = Recording{};
            m_practiceMarks.clear();
            m_practiceRecording = false;
            m_practiceResume = false;
            setMode(Mode::Idle);
            break;""")
    change("src/Lab.cpp", """void Lab::onResetBefore() {
    if (m_layer && m_layer->m_isPracticeMode &&
        (m_mode == Mode::Recording || m_mode == Mode::Playing)) {
        notify("Practice mode stops Frame Window Lab.", NotificationIcon::Warning);
        stop();
    }
    if (m_mode == Mode::Scanning && !m_scan.ownReset) {
        // Restart button, practice toggle...: handled on the next scan frame,
        // not inside the game's reset.
        m_scan.externalReset = true;
    }
    m_tick = 0;
    m_lastInjectedTick = -1;
    m_accumulator = 0.0;
    m_died = false;
    m_reachedEnd = false;
    m_stalled = false;
    m_held.clear();
    if (m_mode == Mode::Recording) m_live.inputs.clear();
    if (m_mode == Mode::Playing) {
        if (auto overlay = Overlay::get()) overlay->resetPlayback();
    }
}

void Lab::onResetAfter() {
    // Inputs the game re-applies during the reset (a held button) were
    // stamped at tick 0 already; make sure the first step is tick 0 too.
    m_tick = 0;
    m_lastInjectedTick = -1;
}""", """void Lab::onPracticeCheckpointStored(CheckpointObject* checkpoint) {
    if (!checkpoint || !m_layer || m_mode != Mode::Recording ||
        !m_practiceRecording || !m_layer->m_isPracticeMode ||
        m_initialRecordingReset) return;
    // A checkpoint commits the successful prefix of the macro.
    std::erase_if(m_practiceMarks, [checkpoint](PracticeMark const& mark) {
        return mark.checkpoint == checkpoint;
    });
    m_practiceMarks.push_back({checkpoint, m_tick, m_live.inputs.size(), m_held});
}

void Lab::onPracticeCheckpointsChanged() {
    if (!m_layer || !m_layer->m_checkpointArray) {
        m_practiceMarks.clear();
        return;
    }
    auto* checkpoints = m_layer->m_checkpointArray;
    std::erase_if(m_practiceMarks, [checkpoints](PracticeMark const& mark) {
        for (unsigned int i = 0; i < checkpoints->count(); ++i) {
            if (checkpoints->objectAtIndex(i) == mark.checkpoint) return false;
        }
        return true;
    });
}

void Lab::onResetBefore() {
    m_practiceResume = false;
    if (m_mode == Mode::Recording && m_practiceRecording &&
        !m_initialRecordingReset && m_layer && m_layer->m_isPracticeMode) {
        // A death must not erase the inputs before the last checkpoint.
        auto* checkpoints = m_layer->m_checkpointArray;
        if (checkpoints && checkpoints->count()) {
            auto* active = checkpoints->lastObject();
            auto it = std::find_if(m_practiceMarks.rbegin(), m_practiceMarks.rend(),
                [active](PracticeMark const& mark) { return mark.checkpoint == active; });
            if (it != m_practiceMarks.rend() && it->inputCount <= m_live.inputs.size()) {
                m_live.inputs.resize(it->inputCount);
                m_practiceResumeTick = it->tick;
                m_practiceResumeHeld = it->held;
                m_practiceResume = true;
                const auto keep = it->inputCount;
                std::erase_if(m_practiceMarks, [keep](PracticeMark const& mark) {
                    return mark.inputCount > keep;
                });
            }
        }
    }
    if (m_mode == Mode::Scanning && !m_scan.ownReset) {
        m_scan.externalReset = true;
    }
    m_tick = 0;
    m_lastInjectedTick = -1;
    m_accumulator = 0.0;
    m_died = false;
    m_reachedEnd = false;
    m_stalled = false;
    m_held.clear();
    if (m_mode == Mode::Recording && !m_practiceResume) {
        m_live.inputs.clear();
        if (m_practiceRecording) m_practiceMarks.clear();
    }
    if (m_mode == Mode::Playing) {
        if (auto overlay = Overlay::get()) overlay->resetPlayback();
    }
}

void Lab::onResetAfter() {
    // The final macro is a single continuous timeline across checkpoint retries.
    m_tick = m_practiceResume ? m_practiceResumeTick : 0;
    m_lastInjectedTick = m_tick - 1;
    if (m_practiceResume) m_held = m_practiceResumeHeld;
    m_practiceResume = false;
}""")
    change("src/Lab.cpp", """    m_live = Recording{};

    if (auto res = saveRecording(*m_recording); !res)""", """    m_live = Recording{};
    m_practiceMarks.clear();
    m_practiceRecording = false;

    if (auto res = saveRecording(*m_recording); !res)""")
    change("src/main.cpp", """    void resetLevel() {
        auto& lab = Lab::get();
        bool ours = lab.attached(this);
        if (ours) lab.onResetBefore();
        PlayLayer::resetLevel();
        if (ours) lab.onResetAfter();
    }
""", """    void resetLevel() {
        auto& lab = Lab::get();
        bool ours = lab.attached(this);
        if (ours) lab.onResetBefore();
        PlayLayer::resetLevel();
        if (ours) lab.onResetAfter();
    }

    void storeCheckpoint(CheckpointObject* checkpoint) {
        PlayLayer::storeCheckpoint(checkpoint);
        auto& lab = Lab::get();
        if (lab.attached(this)) lab.onPracticeCheckpointStored(checkpoint);
    }

    void removeCheckpoint(bool first) {
        PlayLayer::removeCheckpoint(first);
        auto& lab = Lab::get();
        if (lab.attached(this)) lab.onPracticeCheckpointsChanged();
    }
""")
    change("src/Menu.cpp", 'line2 = "Press Record and beat the level once.";',
           'line2 = "Record in normal or practice; beat to save.";')
    change("src/Menu.cpp", 'line3 = "Recording now. Beat the level to save it.";',
           'line3 = "Recording. Practice retries keep checkpoints.";')
    change("src/Menu.cpp", """            "<cy>Record</c>: beat the level once; every click is saved with its tick.\\n"
            "<cg>Scan</c>: each click is replayed earlier and later, one tick at a time, "
            "to find how many frames it could have been on.\\n"
            "<cl>Play</c>: watch the run back with circles, counters and sounds.\\n\\n"
            "Recording and playback run the physics at 240 steps a second. "
            "Platformer levels and practice mode are not supported.",""", """            "<cy>Record</c>: normal OR practice mode. Checkpoints keep your "
            "successful inputs; retrying replaces only the failed suffix.\\n"
            "Beat the level to save the combined macro.\\n"
            "<cg>Scan</c>: test each window by replaying from the start.\\n"
            "<cl>Play</c>: watch the run with circles, counters and sounds.\\n\\n"
            "For reliable windows, the combined macro must replay without "
            "practice checkpoints. Platformer is unsupported.",""")
    print("Applied Iris's Counter practice recording patch.")

if __name__ == "__main__":
    main()
