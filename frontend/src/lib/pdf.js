// Every download in the app is a PDF: lists, the weekly report and the manual-check list.
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { META } from './data'

const TEAL = [20, 85, 92]
const INK = [31, 42, 54]
const MUTED = [102, 114, 127]

const stamp = () => new Date().toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

function header(doc, title, subtitle) {
  const w = doc.internal.pageSize.getWidth()
  doc.setFillColor(...TEAL)
  doc.rect(0, 0, w, 54, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(15)
  doc.text(title, 40, 26)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.text(`${META.college}, ${META.semester}, week ${META.week} of ${META.weeks}`, 40, 42)
  doc.text(`Generated ${stamp()}`, w - 40, 42, { align: 'right' })
  let y = 76
  if (subtitle) {
    doc.setTextColor(...MUTED)
    doc.setFontSize(10)
    const lines = doc.splitTextToSize(subtitle, w - 80)
    doc.text(lines, 40, y)
    y += lines.length * 13 + 6
  }
  return y
}

function footer(doc) {
  const n = doc.getNumberOfPages()
  const w = doc.internal.pageSize.getWidth()
  const h = doc.internal.pageSize.getHeight()
  for (let i = 1; i <= n; i++) {
    doc.setPage(i)
    doc.setFontSize(8.5)
    doc.setTextColor(...MUTED)
    doc.text('EarlySignal. Scores support conversations with students; they never decide anything on their own.', 40, h - 20)
    doc.text(`Page ${i} of ${n}`, w - 40, h - 20, { align: 'right' })
  }
}

const tableStyle = {
  styles: { font: 'helvetica', fontSize: 8.5, cellPadding: 4, textColor: INK, lineColor: [221, 227, 233], lineWidth: 0.5 },
  headStyles: { fillColor: [233, 245, 242], textColor: INK, fontStyle: 'bold' },
  alternateRowStyles: { fillColor: [248, 251, 250] },
  margin: { left: 40, right: 40 },
}

function section(doc, y, title) {
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(12)
  doc.setTextColor(...INK)
  doc.text(title, 40, y)
  doc.setFont('helvetica', 'normal')
  return y + 8
}

export function tablePdf({ title, subtitle, head, rows, file, landscape = true }) {
  const doc = new jsPDF({ orientation: landscape ? 'landscape' : 'portrait', unit: 'pt', format: 'a4' })
  const y = header(doc, title, subtitle)
  autoTable(doc, { ...tableStyle, startY: y, head: [head], body: rows })
  footer(doc)
  doc.save(file)
}

// The weekly report (Round 1 "Generate report"), as a PDF
export function weeklyReport({ scope, kpis, risk, groups, effects, file }) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' })
  let y = header(doc, 'EarlySignal weekly report', `Covers ${scope}.`)
  autoTable(doc, { ...tableStyle, startY: y, head: [kpis.map((k) => k[0])], body: [kpis.map((k) => String(k[1]))] })
  y = doc.lastAutoTable.finalY + 26
  y = section(doc, y, 'Highest-risk students')
  autoTable(doc, { ...tableStyle, startY: y, head: [['Name', 'Roll no', 'Class', 'Chance of failing', 'Main reason', 'Mentor']], body: risk })
  y = doc.lastAutoTable.finalY + 26
  y = section(doc, y, 'Student groups and first action')
  autoTable(doc, { ...tableStyle, startY: y, head: [['Group', 'Students', 'First action']], body: groups })
  y = doc.lastAutoTable.finalY + 26
  y = section(doc, y, 'What worked in past semesters')
  autoTable(doc, { ...tableStyle, startY: y, head: [['Action', 'Students', 'Failed', 'Expected without action']], body: effects })
  footer(doc)
  doc.save(file)
}
