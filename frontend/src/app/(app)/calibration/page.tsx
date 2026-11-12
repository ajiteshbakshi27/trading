"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import CalibrationView from "@/components/parakh/CalibrationView";
import { ErrorBox, Loading } from "@/components/parakh/ui";

export default function CalibrationPage() {
  const [c, setC] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/api/parakh/calibration").then(setC).catch((e) => setErr(e.message)); }, []);
  if (err) return <ErrorBox message={err} />;
  if (!c) return <Loading />;
  return <CalibrationView c={c} />;
}
