export type ComplianceAlertLike = { id: string; title: string; detail: string };

/** Hospital names from the "no patients registered" style compliance alerts. */
export function collectHospitalNamesFromComplianceAlerts(alerts: ComplianceAlertLike[]): string[] {
  const names: string[] = [];
  for (const a of alerts) {
    if (a.id === "hospitals_no_patients" || /no patients registered/i.test(a.title)) {
      names.push(
        ...a.detail
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      );
    }
  }
  return names;
}

function csvEscapeCell(s: string): string {
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function downloadHospitalNamesCsv(names: string[], filename = "compliance-hospital-names.csv"): void {
  const lines = ["hospital_name", ...names.map(csvEscapeCell)];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
