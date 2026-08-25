# Pick-&-Place demo — a minimal cinnamon-style TwinCAT 3 framework

A small, self-contained automation framework in Structured Text that borrows
[ekvip cinnamon's](https://ekvip.com/en/cinnamon-framework) core ideas, plus one
demo machine built on top of it so you can watch the pattern run.

This is **not** a cinnamon replacement — see *Honest scope* at the bottom.

## The idea in one picture

The whole machine is a **tree of nodes**. One `Cyclic()` call on the root fans
out to everything; one `SetMode()` call pushes the operating mode to everything.

```
Machine                 (FB_Machine      : FB_ModeNode)   <- root
└─ HandlingUnit         (FB_HandlingUnit : FB_ModeNode)   <- owns the sequence
   ├─ Lift              (FB_PneumaticCylinder)            <- device / leaf
   └─ Gripper           (FB_PneumaticCylinder)            <- device / leaf
```

Two node flavours, exactly like cinnamon:

- **`FB_CyclicNode`** — a device or monitored component. Gets `OnCyclic()` every
  scan. Holds its children and registers itself with its parent in `FB_init`.
- **`FB_ModeNode`** (extends cyclic) — a functional unit with process logic. Its
  cycle is dispatched by operating mode to `RunAutomatic` / `RunManual` /
  `RunHoming` / `RunStop`.

## Files

Twelve objects, ~430 lines of Structured Text. Paths below are relative to
`TcProject/PickPlace/PickPlacePlc/`. These are TwinCAT's own XML containers —
the code sits in plain-text `CDATA` blocks, so they read fine on the web too.

| File | Role | cinnamon equivalent |
|------|------|---------------------|
| `Framework/I_Node.TcIO` | interface every node implements | `IObject` (trimmed) |
| `Framework/FB_CyclicNode.TcPOU` | base node: tree + registration + cyclic recursion | `CNM_AbstractCyclicNode` |
| `Framework/FB_ModeNode.TcPOU` | mode dispatch (auto/manual/homing/stop) | `CNM_AbstractModeNode` |
| `Framework/FB_CycleManager.TcPOU` | step engine for sequences | `CNM_CycleManager` |
| `Framework/FB_OpModeHandler.TcPOU` | holds mode, drives the root | `CNM` OpmodeHandler |
| `Framework/E_OpMode.TcDUT`, `E_CmdResult.TcDUT` | enums | — |
| `Framework/GVL_Framework.TcGVL` | constants | — |
| `Devices/FB_PneumaticCylinder.TcPOU` | reusable device driver (also used as the gripper) | a hardware driver |
| `Machine/FB_HandlingUnit.TcPOU` | the pick-&-place sequence | example unit |
| `Machine/FB_Machine.TcPOU` | root node | machine node |
| `Machine/MAIN.TcPOU` | 3 declarations, 2 calls | `MAIN` |

## How the pieces click together

1. **Building the tree is free.** Declaring `fbLift : FB_PneumaticCylinder(ipParent := THIS^, ...)`
   makes the cylinder register itself under the handling unit during `FB_init`.
   No wiring, no init list. `MAIN` just declares `fbMachine` and the whole tree exists.
2. **One tick runs everything.** `fbOpMode.Cyclic()` → `root.SetMode(mode)` →
   `root.Cyclic()`, which runs each node's `OnCyclic()` then recurses into children.
   Parent-before-child ordering matters: the sequence sets device *targets*, then
   the devices actuate in the same scan.
3. **Sequences read like a recipe.** `FB_HandlingUnit.RunAutomatic` is a `CASE`
   over `fbCycle.Step`; `Await(fbLift.Extend())` advances the step when the command
   returns `eDone`, latches on `eError`.
4. **Devices hide the hardware.** A cylinder exposes only `Extend()` / `Retract()`
   returning `E_CmdResult`, and owns its coils, sensors and move-timeout.

## Run it (soft-PLC, no I/O needed)

Every device has `bSimulate := TRUE`, so the end sensors are faked ~500 ms after
each move — the sequence steps by itself even without EtherCAT / mapped I/O.

1. Open `TcProject/PickPlace.sln` in TwinCAT XAE (or TcXaeShell).
2. Build the solution. `MAIN` is already assigned to `PlcTask` (cyclic, 10 ms).
3. Activate Configuration → Login → Run.
4. Watch online: put `MAIN.fbMachine.fbHandling.fbCycle.Step` in a watch window and
   scope `...fbLift.bExtendCoil` / `...fbGripper.bExtendCoil` — you'll see the
   pick-&-place loop cycle. Set `fbOpMode.Mode` to `eStop` to halt.

To drive real hardware: set each device's `bSimulate := FALSE` and map
`bExtendCoil` / `bRetractCoil` / `bExtendedSensor` / `bRetractedSensor` to terminals.

Built against TwinCAT 3.1.4026.25, target `TwinCAT RT (x64)`.

## Use it in your own machine

The framework is six objects; the other six are the example. To build your own
unit, copy the `Framework/` folder into your PLC project and delete
`Devices/` and `Machine/`.

| Keep — the framework | Delete — the example |
|---|---|
| `I_Node`, `FB_CyclicNode`, `FB_ModeNode` | `FB_PneumaticCylinder` |
| `FB_CycleManager`, `FB_OpModeHandler` | `FB_HandlingUnit`, `FB_Machine` |
| `E_OpMode`, `E_CmdResult`, `GVL_Framework` | `MAIN` |

**A new device** extends `FB_CyclicNode` and implements `OnCyclic()`. Give it
commands that return `E_CmdResult` so a sequence can await them:

```iecst
FUNCTION_BLOCK FB_Valve EXTENDS FB_CyclicNode
VAR
    bOpenCoil   : BOOL;
    bOpenSensor : BOOL;
    bTarget     : BOOL;
END_VAR

METHOD PUBLIC Open : E_CmdResult
bTarget := TRUE;
IF bOpenSensor THEN
    Open := E_CmdResult.eDone;
ELSE
    Open := E_CmdResult.eBusy;
END_IF

METHOD PROTECTED OnCyclic
bOpenCoil := bTarget;
```

**A new unit** extends `FB_ModeNode`, declares its devices with
`ipParent := THIS^`, and writes its sequence in `RunAutomatic`:

```iecst
FUNCTION_BLOCK FB_Filling EXTENDS FB_ModeNode
VAR
    fbValve : FB_Valve(ipParent := THIS^, sNodeName := 'Valve');
    fbCycle : FB_CycleManager;
END_VAR

METHOD PROTECTED RunAutomatic
fbCycle.Call(bExecute := TRUE);
CASE fbCycle.Step OF
    0: fbCycle.Await(fbValve.Open());
    1: fbCycle.Await(fbValve.Close());
ELSE
    fbCycle.Restart();
END_CASE
```

That is the whole contract. Declaring `fbValve` with `ipParent := THIS^` is
what puts it in the tree — there is no registration call to forget, and no
init list to keep in sync.

Two rules worth knowing:

- **Parent runs before children.** `OnCyclic()` fires on the node first, then
  recurses. A unit sets device targets and the devices act on them in the same
  scan, so there is no one-cycle lag.
- **`cMaxChildren` is 16.** Raise it in `GVL_Framework` if a node needs more
  direct children. Registration beyond the limit is silently ignored.

## Honest scope — what this is and isn't

- **Is:** a clean, readable core showing cinnamon's architecture (tree, cyclic +
  mode nodes, command results, a step engine, mode handling) on one real sequence.
- **Isn't:** cinnamon. No driver catalogue, no self-building TwinCAT HMI over ADS,
  no EventLogger error framework, no generic collections (lists/trees/sets), no
  recipes/metrics, and — most of all — **not validated on real machines**. Those
  are cinnamon's actual value. For a production line, use cinnamon; use this to
  understand the pattern or to seed a small, purpose-built unit.

## Licence

MIT — see [LICENSE](LICENSE). Use it, change it, ship it.
