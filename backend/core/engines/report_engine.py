"""
ReportEngine — PDF/Markdown report generation for pentest, SOC, and threat intel.
Uses ReportLab for PDF generation following PTES/industry standard structures.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ReportEngine:
    REPORT_DIR = Path("./data/reports")

    def __init__(self):
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        self._styles = getSampleStyleSheet()
        self._custom_styles = self._build_custom_styles()

    # ── Internal style helpers ────────────────────────────────────────────────

    def _build_custom_styles(self) -> dict:
        styles = {}

        styles["Title"] = ParagraphStyle(
            "ReportTitle",
            parent=self._styles["Title"],
            fontSize=28,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=12,
            alignment=TA_CENTER,
        )
        styles["Subtitle"] = ParagraphStyle(
            "ReportSubtitle",
            parent=self._styles["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#16213e"),
            spaceAfter=6,
            alignment=TA_CENTER,
        )
        styles["H1"] = ParagraphStyle(
            "ReportH1",
            parent=self._styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f3460"),
            spaceBefore=18,
            spaceAfter=8,
            borderPad=4,
        )
        styles["H2"] = ParagraphStyle(
            "ReportH2",
            parent=self._styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#533483"),
            spaceBefore=12,
            spaceAfter=6,
        )
        styles["Body"] = ParagraphStyle(
            "ReportBody",
            parent=self._styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
        styles["Code"] = ParagraphStyle(
            "ReportCode",
            parent=self._styles["Code"],
            fontSize=8,
            fontName="Courier",
            backColor=colors.HexColor("#f4f4f4"),
            borderPad=4,
            spaceAfter=6,
        )
        styles["Bullet"] = ParagraphStyle(
            "ReportBullet",
            parent=self._styles["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=20,
            spaceAfter=3,
        )
        styles["Critical"] = ParagraphStyle(
            "Critical",
            parent=self._styles["Normal"],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.HexColor("#c0392b"),
            borderPad=4,
        )
        return styles

    def _cvss_color(self, score: float) -> colors.Color:
        """Return color based on CVSS score."""
        if score >= 9.0:
            return colors.HexColor("#c0392b")   # Critical — red
        elif score >= 7.0:
            return colors.HexColor("#e67e22")   # High — orange
        elif score >= 4.0:
            return colors.HexColor("#f39c12")   # Medium — yellow-orange
        elif score > 0:
            return colors.HexColor("#27ae60")   # Low — green
        else:
            return colors.HexColor("#95a5a6")   # Info — grey

    def _severity_from_score(self, score: float) -> str:
        if score >= 9.0:
            return "CRITICAL"
        elif score >= 7.0:
            return "HIGH"
        elif score >= 4.0:
            return "MEDIUM"
        elif score > 0:
            return "LOW"
        return "INFO"

    # ── Table builders ────────────────────────────────────────────────────────

    def _build_severity_table(self, findings: list) -> Table:
        """CVSS-sorted findings table with color coding."""
        headers = ["#", "Title", "Severity", "CVSS", "Affected Component"]
        data = [headers]

        sorted_findings = sorted(
            findings,
            key=lambda f: float(f.get("cvss_score", 0)),
            reverse=True,
        )

        for i, finding in enumerate(sorted_findings, 1):
            score = float(finding.get("cvss_score", 0))
            severity = finding.get("severity") or self._severity_from_score(score)
            data.append([
                str(i),
                finding.get("title", "Unknown")[:60],
                severity,
                f"{score:.1f}" if score > 0 else "N/A",
                finding.get("component", finding.get("target", "Unknown"))[:40],
            ])

        col_widths = [0.4 * inch, 2.8 * inch, 1.0 * inch, 0.7 * inch, 2.1 * inch]
        table = Table(data, colWidths=col_widths)

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]

        # Color-code severity column
        for i, finding in enumerate(sorted_findings, 1):
            score = float(finding.get("cvss_score", 0))
            cell_color = self._cvss_color(score)
            style_cmds.append(("BACKGROUND", (2, i), (2, i), cell_color))
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i), colors.white))

        table.setStyle(TableStyle(style_cmds))
        return table

    def _build_metadata_table(self, data: dict) -> Table:
        rows = [[k, str(v)] for k, v in data.items()]
        table = Table(rows, colWidths=[2 * inch, 4.5 * inch])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    # ── Cover page builder ────────────────────────────────────────────────────

    def _cover_page(self, title: str, subtitle: str, metadata: dict) -> list:
        elements = []
        elements.append(Spacer(1, 1.5 * inch))

        # Header bar
        elements.append(Table(
            [[Paragraph("L'OEIL DE DIEU — AEGIS AI", ParagraphStyle(
                "Cover", fontSize=12, textColor=colors.white, alignment=TA_CENTER))]],
            colWidths=[6.5 * inch],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1a1a2e")),
                               ("TOPPADDING", (0, 0), (-1, -1), 10),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]),
        ))
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(Paragraph(title, self._custom_styles["Title"]))
        elements.append(Paragraph(subtitle, self._custom_styles["Subtitle"]))
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#e74c3c")))
        elements.append(Spacer(1, 0.4 * inch))

        if metadata:
            elements.append(self._build_metadata_table(metadata))

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(
            "CONFIDENTIAL — FOR AUTHORIZED PERSONNEL ONLY",
            ParagraphStyle("conf", fontSize=9, textColor=colors.HexColor("#c0392b"),
                           alignment=TA_CENTER),
        ))
        elements.append(PageBreak())
        return elements

    # ── MODULE 11: Generate pentest report ────────────────────────────────────

    def generate_pentest_report(self, job_data: dict, fmt: str = "pdf") -> str:
        """
        Generate full pentest report following PTES structure:
        1. Cover page — target, date, classification
        2. Executive Summary
        3. Scope and Methodology
        4. Findings sorted by CVSS score
        5. Technical Evidence — nmap outputs, exploit results
        6. Remediation Recommendations
        7. Appendices — raw tool outputs
        Returns path to generated file.
        """
        report_id = str(uuid.uuid4())[:8]
        target = job_data.get("target", "Unknown Target")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"pentest_{target.replace('.', '_').replace('/', '_')}_{timestamp}_{report_id}.pdf"
        filepath = self.REPORT_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = []

        # ── 1. Cover Page ─────────────────────────────────────────────────────
        elements += self._cover_page(
            title="PENETRATION TEST REPORT",
            subtitle=f"Target: {target}",
            metadata={
                "Target": target,
                "Report Date": datetime.utcnow().strftime("%Y-%m-%d"),
                "Classification": job_data.get("classification", "CONFIDENTIAL"),
                "Report ID": report_id,
                "Prepared By": "L'Œil de Dieu — AEGIS AI",
                "Status": job_data.get("status", "Completed"),
            },
        )

        # ── 2. Executive Summary ──────────────────────────────────────────────
        elements.append(Paragraph("1. Executive Summary", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))

        summary = job_data.get("summary", {})
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except Exception:
                summary = {"overview": summary}

        exec_summary = job_data.get("executive_summary", summary.get("overview", ""))
        if exec_summary:
            elements.append(Paragraph(str(exec_summary), self._custom_styles["Body"]))
        else:
            elements.append(Paragraph(
                f"A penetration test was conducted against {target}. "
                "This report documents all findings, evidence collected, and remediation recommendations.",
                self._custom_styles["Body"],
            ))

        # Risk summary counts
        findings = job_data.get("findings", [])
        critical = sum(1 for f in findings if float(f.get("cvss_score", 0)) >= 9.0)
        high     = sum(1 for f in findings if 7.0 <= float(f.get("cvss_score", 0)) < 9.0)
        medium   = sum(1 for f in findings if 4.0 <= float(f.get("cvss_score", 0)) < 7.0)
        low      = sum(1 for f in findings if 0 < float(f.get("cvss_score", 0)) < 4.0)

        risk_data = [
            ["Critical", "High", "Medium", "Low"],
            [str(critical), str(high), str(medium), str(low)],
        ]
        risk_table = Table(risk_data, colWidths=[1.5 * inch] * 4)
        risk_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#c0392b")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e67e22")),
            ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#f39c12")),
            ("BACKGROUND", (3, 0), (3, 0), colors.HexColor("#27ae60")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 1, colors.white),
        ]))
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(risk_table)
        elements.append(Spacer(1, 0.2 * inch))

        # ── 3. Scope and Methodology ──────────────────────────────────────────
        elements.append(Paragraph("2. Scope and Methodology", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(
            f"<b>Scope:</b> {job_data.get('scope', target)}",
            self._custom_styles["Body"],
        ))
        methodology = job_data.get("methodology", (
            "Reconnaissance → Port Scanning → Service Enumeration → "
            "Vulnerability Identification → Exploitation → Post-Exploitation → Reporting"
        ))
        elements.append(Paragraph(f"<b>Methodology:</b> {methodology}", self._custom_styles["Body"]))

        steps = job_data.get("steps", [])
        if steps:
            elements.append(Paragraph("Assessment Phases Executed:", self._custom_styles["H2"]))
            for step in steps:
                name   = step.get("name", "")
                status = step.get("status", "")
                dur    = step.get("duration", 0)
                elements.append(Paragraph(
                    f"• <b>{name}</b> — Status: {status}" + (f", Duration: {dur:.1f}s" if dur else ""),
                    self._custom_styles["Bullet"],
                ))

        elements.append(PageBreak())

        # ── 4. Findings ───────────────────────────────────────────────────────
        elements.append(Paragraph("3. Findings", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))

        if findings:
            elements.append(self._build_severity_table(findings))
            elements.append(Spacer(1, 0.2 * inch))

            sorted_findings = sorted(findings, key=lambda f: float(f.get("cvss_score", 0)), reverse=True)
            for i, finding in enumerate(sorted_findings, 1):
                score = float(finding.get("cvss_score", 0))
                sev   = finding.get("severity") or self._severity_from_score(score)
                clr   = self._cvss_color(score)

                heading_style = ParagraphStyle(
                    f"fh{i}", parent=self._custom_styles["H2"],
                    textColor=clr,
                )
                elements.append(Paragraph(
                    f"3.{i}  [{sev}] {finding.get('title', 'Untitled Finding')}",
                    heading_style,
                ))
                if finding.get("description"):
                    elements.append(Paragraph(
                        f"<b>Description:</b> {finding['description']}",
                        self._custom_styles["Body"],
                    ))
                if finding.get("cvss_score"):
                    elements.append(Paragraph(
                        f"<b>CVSS Score:</b> {score:.1f}  |  <b>Vector:</b> {finding.get('cvss_vector', 'N/A')}",
                        self._custom_styles["Body"],
                    ))
                if finding.get("cve_id"):
                    elements.append(Paragraph(
                        f"<b>CVE:</b> {finding['cve_id']}",
                        self._custom_styles["Body"],
                    ))
                if finding.get("evidence"):
                    elements.append(Paragraph("<b>Evidence:</b>", self._custom_styles["Body"]))
                    elements.append(Paragraph(str(finding["evidence"])[:800], self._custom_styles["Code"]))
                elements.append(Spacer(1, 0.1 * inch))
        else:
            elements.append(Paragraph("No findings recorded.", self._custom_styles["Body"]))

        elements.append(PageBreak())

        # ── 5. Technical Evidence ─────────────────────────────────────────────
        elements.append(Paragraph("4. Technical Evidence", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))

        raw_outputs = job_data.get("raw_outputs", {})
        if raw_outputs:
            for tool, output in raw_outputs.items():
                elements.append(Paragraph(f"4.x  {tool.upper()} Output", self._custom_styles["H2"]))
                out_str = str(output)[:2000]
                elements.append(Paragraph(out_str, self._custom_styles["Code"]))
                elements.append(Spacer(1, 0.1 * inch))
        else:
            # Use steps outputs as evidence
            for step in steps:
                if step.get("output"):
                    elements.append(Paragraph(f"  {step.get('name', '')}", self._custom_styles["H2"]))
                    elements.append(Paragraph(step["output"][:1500], self._custom_styles["Code"]))
                    elements.append(Spacer(1, 0.1 * inch))

        elements.append(PageBreak())

        # ── 6. Remediation Recommendations ───────────────────────────────────
        elements.append(Paragraph("5. Remediation Recommendations", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))

        remediations = job_data.get("remediations", [])
        if remediations:
            for i, rem in enumerate(remediations, 1):
                elements.append(Paragraph(f"• {rem}", self._custom_styles["Bullet"]))
        elif findings:
            sorted_findings = sorted(findings, key=lambda f: float(f.get("cvss_score", 0)), reverse=True)
            for finding in sorted_findings:
                if finding.get("remediation"):
                    elements.append(Paragraph(
                        f"• <b>{finding.get('title','')}</b>: {finding['remediation']}",
                        self._custom_styles["Bullet"],
                    ))
        else:
            elements.append(Paragraph(
                "Apply vendor security patches promptly. Follow the principle of least privilege. "
                "Implement network segmentation. Enable logging and monitoring.",
                self._custom_styles["Body"],
            ))

        elements.append(PageBreak())

        # ── 7. Appendices ─────────────────────────────────────────────────────
        elements.append(Paragraph("6. Appendices", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(
            f"Raw tool output and full scan data for job generated on "
            f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.",
            self._custom_styles["Body"],
        ))

        # ── Build PDF ─────────────────────────────────────────────────────────
        doc.build(elements)
        return str(filepath)

    # ── SOC Incident Report ───────────────────────────────────────────────────

    def generate_soc_incident_report(self, incident_data: dict) -> str:
        """SOC incident report with timeline, IOCs, and remediation steps."""
        report_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        title = incident_data.get("title", "Incident")
        filename = f"incident_{timestamp}_{report_id}.pdf"
        filepath = self.REPORT_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            rightMargin=0.75 * inch, leftMargin=0.75 * inch,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        )
        elements = []

        # Cover
        elements += self._cover_page(
            title="SOC INCIDENT REPORT",
            subtitle=title,
            metadata={
                "Incident ID": incident_data.get("incident_uuid", report_id),
                "Severity": incident_data.get("severity", "HIGH"),
                "Status": incident_data.get("status", "INVESTIGATING"),
                "Date": datetime.utcnow().strftime("%Y-%m-%d"),
                "Prepared By": "AEGIS AI SOC Engine",
            },
        )

        # Summary
        elements.append(Paragraph("1. Incident Summary", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Paragraph(
            incident_data.get("description", "No description provided."),
            self._custom_styles["Body"],
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Timeline
        elements.append(Paragraph("2. Incident Timeline", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        timeline = incident_data.get("timeline", [])
        if timeline:
            for event in timeline:
                ts  = event.get("timestamp", "")
                evt = event.get("event", "")
                elements.append(Paragraph(f"• <b>{ts}</b> — {evt}", self._custom_styles["Bullet"]))
        else:
            elements.append(Paragraph("No timeline data available.", self._custom_styles["Body"]))
        elements.append(Spacer(1, 0.2 * inch))

        # IOCs
        elements.append(Paragraph("3. Indicators of Compromise (IOCs)", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        iocs = incident_data.get("iocs", [])
        if iocs:
            ioc_data = [["Type", "Value", "Confidence"]]
            for ioc in iocs:
                if isinstance(ioc, dict):
                    ioc_data.append([ioc.get("type", ""), ioc.get("value", ""), ioc.get("confidence", "")])
                else:
                    ioc_data.append(["", str(ioc), ""])
            ioc_table = Table(ioc_data, colWidths=[1.5 * inch, 3.5 * inch, 1.5 * inch])
            ioc_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(ioc_table)
        else:
            elements.append(Paragraph("No IOCs extracted.", self._custom_styles["Body"]))
        elements.append(Spacer(1, 0.2 * inch))

        # Remediation
        elements.append(Paragraph("4. Remediation Steps", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        for step in incident_data.get("remediation_steps", ["See analyst notes."]):
            elements.append(Paragraph(f"• {step}", self._custom_styles["Bullet"]))

        doc.build(elements)
        return str(filepath)

    # ── Vulnerability Report ──────────────────────────────────────────────────

    def generate_vulnerability_report(self, cves: list, target: str) -> str:
        """CVE/vulnerability assessment report."""
        report_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename  = f"vulns_{target.replace('.', '_')}_{timestamp}_{report_id}.pdf"
        filepath  = self.REPORT_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            rightMargin=0.75 * inch, leftMargin=0.75 * inch,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        )
        elements = []

        elements += self._cover_page(
            title="VULNERABILITY ASSESSMENT REPORT",
            subtitle=f"Target: {target}",
            metadata={
                "Target": target,
                "CVE Count": len(cves),
                "Report Date": datetime.utcnow().strftime("%Y-%m-%d"),
                "Report ID": report_id,
            },
        )

        elements.append(Paragraph("1. Vulnerability Summary", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))

        if cves:
            findings = [
                {
                    "title": c.get("cve_id", c.get("id", "Unknown CVE")),
                    "cvss_score": c.get("cvss_score", c.get("score", 0)),
                    "description": c.get("description", ""),
                    "component": target,
                    "severity": c.get("severity", ""),
                }
                for c in cves
            ]
            elements.append(self._build_severity_table(findings))
            elements.append(Spacer(1, 0.2 * inch))
            elements.append(Paragraph("2. CVE Details", self._custom_styles["H1"]))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
            for cve in sorted(cves, key=lambda c: float(c.get("cvss_score", c.get("score", 0))), reverse=True):
                cve_id = cve.get("cve_id", cve.get("id", ""))
                score  = float(cve.get("cvss_score", cve.get("score", 0)))
                clr    = self._cvss_color(score)
                heading_style = ParagraphStyle(f"cveh_{cve_id}", parent=self._custom_styles["H2"], textColor=clr)
                elements.append(Paragraph(f"{cve_id} — CVSS {score:.1f}", heading_style))
                elements.append(Paragraph(cve.get("description", "")[:500], self._custom_styles["Body"]))
                elements.append(Spacer(1, 0.1 * inch))
        else:
            elements.append(Paragraph("No CVEs found.", self._custom_styles["Body"]))

        doc.build(elements)
        return str(filepath)

    # ── Weekly Threat Report ──────────────────────────────────────────────────

    def generate_weekly_threat_report(self, threat_data: dict) -> str:
        """Weekly threat intelligence summary report."""
        report_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename  = f"weekly_threat_{timestamp}_{report_id}.pdf"
        filepath  = self.REPORT_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            rightMargin=0.75 * inch, leftMargin=0.75 * inch,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        )
        elements = []

        week_start = threat_data.get("week_start", "")
        week_end   = threat_data.get("week_end", datetime.utcnow().strftime("%Y-%m-%d"))

        elements += self._cover_page(
            title="WEEKLY THREAT INTELLIGENCE REPORT",
            subtitle=f"Period: {week_start} — {week_end}",
            metadata={
                "Period": f"{week_start} to {week_end}",
                "Total CVEs": threat_data.get("total_cves", 0),
                "Critical CVEs": threat_data.get("critical_cves", 0),
                "CISA KEV New": threat_data.get("cisa_kev_new", 0),
                "Report ID": report_id,
            },
        )

        # Threat summary
        elements.append(Paragraph("1. Threat Landscape Summary", self._custom_styles["H1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
        elements.append(Paragraph(
            threat_data.get("summary", "Automated weekly threat intelligence digest from NVD, CISA KEV, and Exploit-DB."),
            self._custom_styles["Body"],
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Top CVEs
        top_cves = threat_data.get("top_cves", [])
        if top_cves:
            elements.append(Paragraph("2. Top Critical Vulnerabilities", self._custom_styles["H1"]))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
            findings = [
                {
                    "title": c.get("cve_id", c.get("identifier", "")),
                    "cvss_score": c.get("cvss_score", 0),
                    "description": c.get("description", ""),
                    "component": c.get("affected_product", ""),
                    "severity": c.get("severity", ""),
                }
                for c in top_cves
            ]
            elements.append(self._build_severity_table(findings))

        # Active exploits
        exploits = threat_data.get("exploits", [])
        if exploits:
            elements.append(Spacer(1, 0.2 * inch))
            elements.append(Paragraph("3. Active Public Exploits", self._custom_styles["H1"]))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
            for exp in exploits[:15]:
                title = exp.get("title", exp.get("identifier", ""))
                date  = exp.get("published_at", "")
                elements.append(Paragraph(f"• <b>{title}</b>" + (f" ({date})" if date else ""), self._custom_styles["Bullet"]))

        doc.build(elements)
        return str(filepath)
