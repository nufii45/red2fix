import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { interpolate } from "remotion";

export const SANS = loadInter("normal", { weights: ["400", "600", "800"], subsets: ["latin"] }).fontFamily;
export const MONO = loadMono("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily;

// Dark-mode tokens from web/app/globals.css, so the video matches the try-it site.
export const C = {
  bg: "#0c0c0f",
  ink: "#f4f4f5",
  g200: "#2a2a30",
  g300: "#3a3a42",
  g400: "#8a8a92",
  g600: "#c4c4cc",
  pass: "#4ade80",
  fail: "#ff7a6e",
};

export const fade = (frame: number, start: number, d = 15) =>
  interpolate(frame, [start, start + d], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
