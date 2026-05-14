'use client';

import React, { useState } from 'react';
import SearchableSelect from './SearchableSelect';

// Example interfaces
interface ICD10Code {
  id: string;
  description: string;
}

interface Drug {
  id: string;
  name: string;
}

interface Role {
  id: string;
  name: string;
}

/**
 * Example usage of SearchableSelect component
 * This demonstrates the component's capabilities
 */
export function SearchableSelectExamples(): React.ReactElement {
  // ICD-10 selector example
  const [selectedCode, setSelectedCode] = useState<ICD10Code | undefined>();
  const icd10Codes: ICD10Code[] = [
    { id: 'A01.0', description: 'Typhoid fever' },
    { id: 'A01.1', description: 'Paratyphoid fever' },
    { id: 'A02.0', description: 'Salmonella infection' },
  ];

  // Drug selector example
  const [selectedDrug, setSelectedDrug] = useState<Drug | undefined>();
  const drugs: Drug[] = [
    { id: 'amoxicillin', name: 'Amoxicillin' },
    { id: 'ibuprofen', name: 'Ibuprofen' },
    { id: 'lisinopril', name: 'Lisinopril' },
  ];

  // Multi-select roles example
  const [selectedRoles, setSelectedRoles] = useState<Role[]>([]);
  const roles: Role[] = [
    { id: 'doctor', name: 'Doctor' },
    { id: 'nurse', name: 'Nurse' },
    { id: 'lab_tech', name: 'Lab Technician' },
  ];

  return (
    <div className="space-y-8 p-8">
      {/* ICD-10 Selector */}
      <div>
        <h2 className="text-lg font-semibold mb-2">ICD-10 Code Selector</h2>
        <SearchableSelect
          options={icd10Codes}
          value={selectedCode}
          onChange={(val) => setSelectedCode(val as ICD10Code)}
          getLabel={(code) => `${code.id} - ${code.description}`}
          getValue={(code) => code.id}
          placeholder="Search ICD-10 codes..."
          searchable
          clearable
        />
        {selectedCode && (
          <div className="mt-2 p-2 bg-blue-50 rounded text-sm">
            Selected: {selectedCode.id} - {selectedCode.description}
          </div>
        )}
      </div>

      {/* Drug Selector */}
      <div>
        <h2 className="text-lg font-semibold mb-2">Drug Selector</h2>
        <SearchableSelect
          options={drugs}
          value={selectedDrug}
          onChange={(val) => setSelectedDrug(val as Drug)}
          getLabel={(drug) => drug.name}
          getValue={(drug) => drug.id}
          placeholder="Search drugs..."
          searchable
          clearable
        />
        {selectedDrug && (
          <div className="mt-2 p-2 bg-blue-50 rounded text-sm">
            Selected: {selectedDrug.name}
          </div>
        )}
      </div>

      {/* Multi-select Roles */}
      <div>
        <h2 className="text-lg font-semibold mb-2">Role Selector (Multi-select)</h2>
        <SearchableSelect
          options={roles}
          value={selectedRoles}
          onChange={(val) => setSelectedRoles(val as Role[])}
          getLabel={(role) => role.name}
          getValue={(role) => role.id}
          placeholder="Select roles..."
          multi
          searchable
          clearable
        />
        {selectedRoles.length > 0 && (
          <div className="mt-2 p-2 bg-blue-50 rounded text-sm">
            Selected: {selectedRoles.map((r) => r.name).join(', ')}
          </div>
        )}
      </div>

      {/* Disabled state */}
      <div>
        <h2 className="text-lg font-semibold mb-2">Disabled Selector</h2>
        <SearchableSelect
          options={drugs}
          value={selectedDrug}
          onChange={(val) => setSelectedDrug(val as Drug)}
          disabled
          placeholder="This is disabled..."
        />
      </div>
    </div>
  );
}
