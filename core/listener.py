'''
快捷键监听器
'''
from collections.abc import Callable

from pynput import keyboard

KeyType = keyboard.Key | keyboard.KeyCode | None


class thePressedKeySet:
    """用于存储当前按下的键的组合(可以只用一个键，也可以是多个键的组合)"""

    def __init__(self):
        self.pressed_keys = set()

    def addkey(self, key):
        self.pressed_keys.add(key)

    def removekey(self, key):
        self.pressed_keys.discard(key)

    def clearKeys(self):
        self.pressed_keys.clear()

    def getPressedKeys(self):
        return self.pressed_keys

    def destroy(self):
        self.pressed_keys.clear()


class KeyboardListener:
    """键盘监听器：只负责监听按键，不直接处理业务动作。"""
    def __init__(
        self,
        on_key_press: Callable[[KeyType, thePressedKeySet], None] | None = None,
        on_key_release: Callable[[KeyType, thePressedKeySet], None] | None = None,
    ):
        self.on_key_press_callback = on_key_press
        self.on_key_release_callback = on_key_release
        self.pressedKey = thePressedKeySet()
        self.listener = None

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.listener.start()
        return self.listener

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
        self.pressedKey.destroy()

    def _on_press(self, key: KeyType) -> None:
        self.pressedKey.addkey(key)
        if self.on_key_press_callback:
            self.on_key_press_callback(key, self.pressedKey)

    def _on_release(self, key: KeyType) -> None:
        self.pressedKey.removekey(key)
        if self.on_key_release_callback:
            self.on_key_release_callback(key, self.pressedKey)
        # if key == keyboard.Key.esc:
        #     self.stop()
