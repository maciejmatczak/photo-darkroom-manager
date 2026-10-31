"""Exercise the actual NiceGUI form and action rows against temporary roots."""

import asyncio

import pytest
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation

from photo_darkroom_manager.gui.layout import DarkroomUI
from photo_darkroom_manager.gui.node import DarkroomNodeUI
from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.scan import DarkroomNode

pytestmark = pytest.mark.internal


def test_new_batch_form_creates_custom_and_existing_devices(settings) -> None:
    manager = DarkroomManager(settings)
    controller = DarkroomUI(manager)

    async def scenario() -> None:
        async with user_simulation(root=controller.build) as user:
            await user.open("/")
            await user.should_see("Scan complete")
            user.find("New Batch").click()
            select = next(iter(user.find(ui.select).elements))
            assert select.value is None
            user.find("Create").click()
            await user.should_see("Device must be a valid folder name")
            assert list(settings.darkroom.iterdir()) == []

            # This is the value event emitted by the browser for custom input.
            user.find(ui.select).trigger("update:modelValue", "Camera")
            user.find("Year").clear().type("2026")
            user.find("Month").clear().type("10")
            user.find("Create").click()
            await user.should_see("Created batch: 2026-10")
            batch = settings.darkroom / "Camera/2026/2026-10"
            assert (batch / "PUBLISH").is_dir()
            assert batch in controller.registry

            user.find("New Batch").click()
            select = next(iter(user.find(ui.select).elements))
            assert select.options == ["Camera"]
            assert select.value is None
            user.find(ui.select).click()
            user.find("Camera").click()
            assert select.value == "Camera"
            user.find("Year").clear().type("2027")
            user.find("Month").clear().type("1")
            user.find("Create").click()
            await user.should_see("Created batch: 2027-01")
            assert settings.darkroom / "Camera/2027/2027-01" in controller.registry

            user.find("New Batch").click()
            user.find(ui.select).trigger("update:modelValue", "Phone")
            user.find("Year").clear().type("2026")
            user.find("Month").clear().type("10")
            user.find("Create").click()
            # "Created batch: 2026-10" and "Phone" are already visible (Camera's
            # notification, the typed device), so wait for the folder instead.
            # A new device has no registered ancestor, so the tree fully refreshes.
            phone = settings.darkroom / "Phone"
            for _ in range(50):
                if phone in controller.registry:
                    break
                await asyncio.sleep(0.05)
            assert (phone / "2026/2026-10/PUBLISH").is_dir()
            assert phone in controller.registry

    asyncio.run(scenario())


def test_device_row_new_batch_preselects_device(settings) -> None:
    (settings.darkroom / "Camera").mkdir()
    (settings.darkroom / "Phone").mkdir()
    controller = DarkroomUI(DarkroomManager(settings))

    async def scenario() -> None:
        async with user_simulation(root=controller.build) as user:
            await user.open("/")
            await user.should_see("Scan complete")
            phone_row = controller.registry[settings.darkroom / "Phone"]
            with user:
                phone_row._controller.show_new_batch_dialog(phone_row.node.name)
            select = next(iter(user.find(ui.select).elements))
            assert select.value == "Phone"
            assert select.options == ["Camera", "Phone"]
            user.find("Year").clear().type("2026")
            user.find("Month").clear().type("10")
            user.find("Create").click()
            batch = settings.darkroom / "Phone/2026/2026-10"
            for _ in range(50):
                if batch in controller.registry:
                    break
                await asyncio.sleep(0.05)
            assert (batch / "PUBLISH").is_dir()
            assert not (settings.darkroom / "Camera/2026").exists()

    asyncio.run(scenario())


def test_action_rows_preserve_scope_and_mapped_links(settings) -> None:
    manager = DarkroomManager(settings)
    manager.new_batch_action("Camera", "2026", "10", None, "Walk").execute(None)
    batch_path = settings.darkroom / "Camera/2026/2026-10 Walk"
    (settings.archive / "2026/2026-10 Walk/Camera").mkdir(parents=True)
    (settings.showroom / "2026/2026-10 Walk/Camera").mkdir(parents=True)
    tree = manager.rescan()
    controller = DarkroomUI(manager)

    async def scenario() -> None:
        async with user_simulation(root=controller.build) as user:
            await user.open("/")
            await user.should_see("Scan complete")

            def buttons(node: DarkroomNode) -> list[ui.button]:
                with user, ui.row() as row:
                    DarkroomNodeUI(node, controller)._action_buttons()
                return [e for e in row.descendants() if isinstance(e, ui.button)]

            device = tree.children[0]
            year = device.children[0]
            batch = year.children[0]
            assert [b.props["icon"] for b in buttons(device)] == ["folder_open", "add"]
            assert [b.props["icon"] for b in buttons(year)] == ["folder_open"]

            batch_actions = buttons(batch)
            assert {"edit", "cleaning_services", "publish", "archive"} <= {
                button.props["icon"] for button in batch_actions
            }
            assert all(button.enabled for button in batch_actions[-2:])

            photos = batch_path / "PHOTOS"
            photos.mkdir()
            subfolder = DarkroomNode(path=photos, name="PHOTOS", node_type="subfolder")
            sub_actions = buttons(subfolder)
            assert not sub_actions[-2].enabled  # flat published output
            assert not sub_actions[-1].enabled  # not archived yet
            publish = DarkroomNode(
                path=batch_path / "PUBLISH", name="PUBLISH", node_type="subfolder"
            )
            assert len(buttons(publish)) == 1

    asyncio.run(scenario())
