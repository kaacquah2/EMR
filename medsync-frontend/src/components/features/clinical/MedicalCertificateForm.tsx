"use client";

import React, { useState } from "react";
import { 
  FileText, 
  Calendar, 
  CheckCircle2, 
  Printer,
  ShieldCheck,
  Stethoscope
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";

interface MedicalCertificateFormProps {
  patient: {
    id: string;
    name: string;
    ghana_health_id: string;
    dob: string;
    gender: 'male' | 'female';
  };
  doctor: {
    name: string;
    licence: string;
  };
  onPrint?: (data: MedicalCertificateData) => void;
}

interface MedicalCertificateData {
  startDate: string;
  endDate: string;
  durationDays: string;
  diagnosis: string;
  fitnessStatus: string;
  additionalNotes: string;
  isPrivate: boolean;
}

/**
 * Medical Certificate (Sick Note) Form
 * 
 * Compliant with GHS standards for medical excuses.
 */
export function MedicalCertificateForm({ patient, doctor, onPrint }: MedicalCertificateFormProps) {
  const [formData, setFormData] = useState({
    startDate: new Date().toISOString().split('T')[0],
    endDate: "",
    durationDays: "1",
    diagnosis: "",
    fitnessStatus: "unfit",
    additionalNotes: "",
    isPrivate: true, // If true, don't show full diagnosis on the printed form
  });

  const [isGenerated, setIsGenerated] = useState(false);

  const handleGenerate = () => {
    setIsGenerated(true);
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {!isGenerated ? (
        <Card className="border-slate-200 dark:border-slate-800 shadow-xl">
          <CardHeader className="border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-[#0EAFBE]/10 rounded-lg">
                <FileText className="h-5 w-5 text-[#0EAFBE]" />
              </div>
              <div>
                <CardTitle className="text-xl">Medical Certificate</CardTitle>
                <p className="text-sm text-slate-500">Generate a formal medical excuse or fitness report.</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            {/* Patient Header (Read Only) */}
            <div className="p-4 bg-slate-50 dark:bg-slate-900 rounded-lg flex justify-between items-center border border-slate-100 dark:border-slate-800">
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase text-slate-400 tracking-wider">Patient</p>
                <p className="font-bold text-slate-900 dark:text-white">{patient.name}</p>
                <p className="text-xs text-slate-500 font-mono">{patient.ghana_health_id}</p>
              </div>
              <Badge variant="default" className="bg-white dark:bg-slate-800">
                {patient.dob}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start-date">Excused From</Label>
                <Input 
                  id="start-date" 
                  type="date" 
                  value={formData.startDate}
                  onChange={(e) => setFormData({...formData, startDate: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="duration">Duration (Days)</Label>
                <Input 
                  id="duration" 
                  type="number" 
                  min="1"
                  value={formData.durationDays}
                  onChange={(e) => setFormData({...formData, durationDays: e.target.value})}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Fitness Status</Label>
              <Select 
                value={formData.fitnessStatus} 
                onChange={(e) => setFormData({...formData, fitnessStatus: e.target.value})}
              >
                <option value="unfit">Unfit for work/school</option>
                <option value="light_duty">Light duty only</option>
                <option value="fit">Fit for work/school</option>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="diagnosis">Diagnosis / Reason</Label>
                <div className="flex items-center gap-2">
                  <input 
                    type="checkbox" 
                    id="is-private" 
                    checked={formData.isPrivate}
                    onChange={(e) => setFormData({...formData, isPrivate: e.target.checked})}
                    className="h-4 w-4 rounded border-slate-300 text-[#0EAFBE] focus:ring-[#0EAFBE]"
                  />
                  <Label htmlFor="is-private" className="text-xs font-normal text-slate-500">
                    Hide diagnosis on print (Medical Privacy)
                  </Label>
                </div>
              </div>
              <Textarea 
                id="diagnosis" 
                placeholder="Briefly state clinical findings..."
                className="min-h-[100px]"
                value={formData.diagnosis}
                onChange={(e) => setFormData({...formData, diagnosis: e.target.value})}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Additional Instructions (Optional)</Label>
              <Textarea 
                id="notes" 
                placeholder="e.g. Bed rest required, Avoid heavy lifting..."
                className="min-h-[80px]"
                value={formData.additionalNotes}
                onChange={(e) => setFormData({...formData, additionalNotes: e.target.value})}
              />
            </div>
          </CardContent>
          <CardFooter className="bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 p-4 justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span>Electronically signed by {doctor.name}</span>
            </div>
            <Button 
              onClick={handleGenerate}
              className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white"
            >
              Preview Certificate
            </Button>
          </CardFooter>
        </Card>
      ) : (
        <Card className="border-slate-200 dark:border-slate-800 shadow-xl print:shadow-none print:border-none">
          <CardContent className="p-12 space-y-8 relative overflow-hidden">
            {/* Watermark for digital security */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-[0.03] rotate-[-30deg] pointer-events-none select-none">
              <p className="text-9xl font-bold font-mono tracking-widest uppercase">MEDSYNC AUTHENTIC</p>
            </div>

            {/* Certificate Header */}
            <div className="text-center space-y-2 border-b-2 border-slate-100 pb-6">
              <p className="text-2xl font-black uppercase tracking-widest text-slate-900 dark:text-white">Medical Certificate</p>
              <p className="text-sm font-medium text-slate-500">CERTIFICATE OF ILLNESS OR FITNESS</p>
            </div>

            {/* Certificate Body */}
            <div className="space-y-6 text-slate-800 dark:text-slate-200 leading-loose">
              <p className="text-lg">
                This is to certify that I have examined <span className="font-bold border-b border-slate-400 px-2">{patient.name}</span>, 
                GHS ID: <span className="font-mono text-sm font-bold border-b border-slate-400 px-1">{patient.ghana_health_id}</span>, 
                on this day <span className="font-medium">{new Date().toLocaleDateString()}</span>.
              </p>

              <p className="text-lg">
                I find that {patient.gender === 'female' ? 'she' : 'he'} is suffering from 
                <span className="font-bold px-2 italic underline decoration-slate-300">
                  {formData.isPrivate ? "a medical condition" : (formData.diagnosis || "a clinical condition")}
                </span>
                and is considered 
                <span className="font-bold px-2 uppercase text-[#0EAFBE]">
                  {formData.fitnessStatus.replace('_', ' ')}
                </span>.
              </p>

              <p className="text-lg">
                I recommend that {patient.gender === 'female' ? 'she' : 'he'} be excused from work/duty for a period of 
                <span className="font-bold px-2 border-b border-slate-400">{formData.durationDays} days</span>, 
                effective from <span className="font-bold px-2 border-b border-slate-400">{formData.startDate}</span>.
              </p>

              {formData.additionalNotes && (
                <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-100 dark:border-slate-800">
                  <p className="text-xs font-bold uppercase text-slate-400 mb-1">Additional Instructions</p>
                  <p className="text-sm italic">{formData.additionalNotes}</p>
                </div>
              )}
            </div>

            {/* Signature Area */}
            <div className="pt-12 flex justify-between items-end">
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-[#0EAFBE] mb-2">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="text-xs font-bold uppercase tracking-tighter italic">Digitally Verified</span>
                </div>
                <p className="text-lg font-black">{doctor.name}</p>
                <p className="text-sm text-slate-500 uppercase tracking-tighter font-medium">Medical Officer / Specialist</p>
                <p className="text-xs font-mono text-slate-400">GMC No: {doctor.licence}</p>
              </div>
              
              <div className="w-32 h-32 opacity-10 grayscale">
                {/* Visual placeholder for hospital stamp */}
                <Stethoscope className="w-full h-full text-slate-900" />
              </div>
            </div>
          </CardContent>
          <CardFooter className="bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 p-4 flex justify-between print:hidden">
            <Button variant="ghost" onClick={() => setIsGenerated(false)}>
              Edit Details
            </Button>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                onClick={() => window.print()}
                className="flex items-center gap-2"
              >
                <Printer className="h-4 w-4" />
                Print Certificate
              </Button>
              <Button 
                onClick={() => onPrint?.(formData)}
                className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white flex items-center gap-2"
              >
                <Calendar className="h-4 w-4" />
                Save to Record
              </Button>
            </div>
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
