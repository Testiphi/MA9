"""Locate complete multiplayer car cards in a normalized 1280x720 list image."""

from __future__ import annotations

import cv2
import numpy as np


CANVAS = (1280, 720)
CARD_TOPS = (195, 432)
CARD_HEIGHT = 227
CARD_WIDTH_RANGE = (446, 460)


def normalize_list_image(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if abs(width / height - 16 / 9) > 0.03:
        raise ValueError(f"expected a 16:9 selection screenshot, got {width}x{height}")
    if (width, height) == CANVAS:
        return image
    return cv2.resize(image, CANVAS, interpolation=cv2.INTER_AREA)


def detect_list_cards(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Use the long top border; discard cropped cards at either screen edge."""
    frame = normalize_list_image(image).astype(np.int16)
    boxes: list[tuple[int, int, int, int]] = []
    for top in CARD_TOPS:
        difference = np.linalg.norm(frame[top] - frame[top - 7], axis=1)
        mask = (difference > 70).astype(np.uint8)
        mask = cv2.morphologyEx(mask[None, :], cv2.MORPH_CLOSE, np.ones((1, 5), np.uint8))[0]
        boundaries = np.diff(np.r_[0, mask, 0].astype(np.int8))
        for left, right in zip(np.flatnonzero(boundaries == 1), np.flatnonzero(boundaries == -1)):
            width = int(right - left)
            if not (CARD_WIDTH_RANGE[0] <= width <= CARD_WIDTH_RANGE[1]):
                continue
            if left < 2 or right > CANVAS[0] - 2:
                continue
            # A second edge across the bottom rejects a long line within the page.
            inside = frame[top + CARD_HEIGHT - 2, left + 60:right - 60]
            outside = frame[top + CARD_HEIGHT + 5, left + 60:right - 60]
            if float(np.median(np.linalg.norm(inside - outside, axis=1))) < 45:
                continue
            boxes.append((int(left), int(top), width, CARD_HEIGHT))
    return sorted(boxes, key=lambda box: (box[1], box[0]))
