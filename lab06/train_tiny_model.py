#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Жижиг гажил илрүүлэгчийг сургаж LiteRT (.tflite) болгох

⚠ ЗӨӨВРИЙН КОМПЬЮТЕР дээр ажиллуулна (TensorFlow шаардлагатай). Pi 3B дээр
  БИШ — Pi дээр зөвхөн дүгнэлт (ai-edge-litert) ажиллана.

    python3 -m venv ~/tf && ~/tf/bin/pip install tensorflow
    ~/tf/bin/python lab06/train_tiny_model.py --data lab06/data --out lab06/models

Юу хийх вэ:
  1. lab06/data/normal-*.csv ба anomaly-*.csv (collect_data.py-ийн гаралт:
     timestamp,proc_temp_c,vibration_g,rpm) → 3 оролттой хүснэгтэн өгөгдөл
  2. Keras: Normalization → Dense(16) → Dense(8) → Dense(1, sigmoid)
     Гаралт = гажлын магадлал 0..1 — edge/agent/edge_agent.py-ийн
     Detector яг ийм загвар хүлээдэг (оролт [1,3] float32 эсвэл int8).
  3. Хоёр файл гаргана (LiteRT-ийн албан ёсны post-training quantization):
       model_float32.tflite  — квантчлалгүй
       model_int8.tflite     — бүрэн бүхэл тоон (full integer) квантчлал:
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.representative_dataset = …
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type  = tf.int8
            converter.inference_output_type = tf.int8

  --mobilenet: Лаб 6-гийн "сөрөг жишээ"-нд зориулж Keras MobileNetV2-ийг
  (224×224×3, ImageNet жин) мөн ижил аргаар бүрэн int8 болгоно →
  mobilenet_224_quant.tflite. Representative dataset нь санамсаргүй зураг
  тул НАРИЙВЧЛАЛ нь утгагүй — зөвхөн СААТАЛ, санах ойг хэмжихэд зориулсан.

Эх сурвалж:
  https://ai.google.dev/edge/litert/conversion/tensorflow/quantization/post_training_quantization
  https://ai.google.dev/edge/litert/conversion/tensorflow/quantization/post_training_integer_quant
  https://www.tensorflow.org/api_docs/python/tf/keras/applications/MobileNetV2
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys

import numpy as np

AXES = ["proc_temp_c", "vibration_g", "rpm"]


def load(data_dir: str) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for label, y in (("normal", 0.0), ("anomaly", 1.0)):
        files = sorted(glob.glob(os.path.join(data_dir, f"{label}-*.csv")))
        if not files:
            sys.exit(f"{data_dir}/{label}-*.csv олдсонгүй — эхлээд collect_data.py")
        for fn in files:
            with open(fn, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        xs.append([float(row[k]) for k in AXES])
                        ys.append(y)
                    except (KeyError, ValueError):
                        continue
    x = np.asarray(xs, dtype=np.float32)
    y = np.asarray(ys, dtype=np.float32)
    print(f"→ {len(x)} дээж (normal={int((y == 0).sum())}, "
          f"anomaly={int((y == 1).sum())})")
    return x, y


def convert(tf, model, rep, out_path: str, int8: bool) -> None:
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    if int8:
        conv.optimizations = [tf.lite.Optimize.DEFAULT]
        conv.representative_dataset = rep
        conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        conv.inference_input_type = tf.int8
        conv.inference_output_type = tf.int8
    data = conv.convert()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"→ {out_path}  ({len(data) / 1024:.1f} KiB)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--data", default="lab06/data")
    p.add_argument("--out", default="lab06/models")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--mobilenet", action="store_true",
                   help="мөн MobileNetV2 224 int8 (сөрөг жишээ) гаргах")
    p.add_argument("--skip-tiny", action="store_true",
                   help="жижиг загварыг алгасах (зөвхөн --mobilenet)")
    a = p.parse_args()

    import tensorflow as tf   # зөвхөн компьютер дээр
    os.makedirs(a.out, exist_ok=True)

    if not a.skip_tiny:
        x, y = load(a.data)
        rng = np.random.default_rng(0)
        idx = rng.permutation(len(x))
        x, y = x[idx], y[idx]
        n_val = max(1, len(x) // 5)
        norm = tf.keras.layers.Normalization(axis=-1)
        norm.adapt(x[n_val:])
        model = tf.keras.Sequential([
            tf.keras.Input(shape=(len(AXES),)),
            norm,
            tf.keras.layers.Dense(16, activation="relu"),
            tf.keras.layers.Dense(8, activation="relu"),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ])
        model.compile(optimizer="adam", loss="binary_crossentropy",
                      metrics=["accuracy"])
        model.fit(x[n_val:], y[n_val:], epochs=a.epochs, batch_size=32,
                  validation_data=(x[:n_val], y[:n_val]), verbose=0)
        _, acc = model.evaluate(x[:n_val], y[:n_val], verbose=0)
        print(f"→ float32 нарийвчлал (validation): {acc * 100:.2f}%  "
              "← Хүснэгт 6.2")

        def rep():
            for i in range(min(300, len(x))):
                yield [x[i:i + 1]]

        convert(tf, model, rep, os.path.join(a.out, "model_float32.tflite"), False)
        convert(tf, model, rep, os.path.join(a.out, "model_int8.tflite"), True)

        # int8 загварын нарийвчлалыг LiteRT interpreter-ээр шалгана
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:                      # хуучин TensorFlow-д байгаа
            Interpreter = tf.lite.Interpreter
        it = Interpreter(model_path=os.path.join(a.out, "model_int8.tflite"))
        it.allocate_tensors()
        inp, out = it.get_input_details()[0], it.get_output_details()[0]
        s_in, z_in = inp["quantization"]
        s_out, z_out = out["quantization"]
        ok = 0
        for xi, yi in zip(x[:n_val], y[:n_val]):
            q = np.clip(np.round(xi / s_in) + z_in, -128, 127).astype(np.int8)
            it.set_tensor(inp["index"], q.reshape(inp["shape"]))
            it.invoke()
            prob = (float(it.get_tensor(out["index"]).ravel()[0]) - z_out) * s_out
            ok += int((prob >= 0.5) == (yi >= 0.5))
        print(f"→ int8 нарийвчлал (validation): {100 * ok / n_val:.2f}%  ← Хүснэгт 6.2")

    if a.mobilenet:
        m = tf.keras.applications.MobileNetV2(input_shape=(224, 224, 3),
                                              weights="imagenet")

        def rep_img():
            rng = np.random.default_rng(1)
            for _ in range(20):
                yield [rng.uniform(-1, 1, (1, 224, 224, 3)).astype(np.float32)]

        convert(tf, m, rep_img, os.path.join(a.out, "mobilenet_224_quant.tflite"), True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
