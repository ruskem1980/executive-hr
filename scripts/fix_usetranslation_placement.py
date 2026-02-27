#!/usr/bin/env python3
"""
Исправляет неправильное размещение useTranslation() в параметрах функций.
Перемещает `const { t } = useTranslation();` из параметров в тело функции.
"""

import re
from pathlib import Path
from typing import List

def fix_file(file_path: Path) -> bool:
    """
    Исправляет один файл.
    Возвращает True если были изменения.
    """
    content = file_path.read_text(encoding='utf-8')
    original_content = content

    # Паттерн: export function NAME({\n  const { t } = useTranslation();\n  остальные параметры
    # Нужно переместить const { t } после закрывающей скобки параметров

    # Используем регулярное выражение с DOTALL для многострочного поиска
    pattern = r'(export function \w+\(\{)\s*const \{ t \} = useTranslation\(\);\s*'

    def replacer(match):
        # Возвращаем только начало функции без const { t }
        return match.group(1) + '\n  '

    # Убираем const { t } из параметров
    content = re.sub(pattern, replacer, content)

    # Теперь нужно добавить const { t } в начало тела функции
    # Находим паттерн: }: TypeProps) {
    # И добавляем после него const { t }

    # Только если была замена в параметрах
    if content != original_content:
        # Находим первую строку после }: Props) {
        pattern2 = r'(\}: \w+Props\) \{)\s*\n'

        def add_translation(match):
            return match.group(1) + '\n  const { t } = useTranslation();\n'

        content = re.sub(pattern2, add_translation, content, count=1)

    if content != original_content:
        file_path.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    # Путь к директории с исходниками
    src_dir = Path('apps/frontend/src')

    # Список всех файлов для исправления (из grep результатов)
    files_to_fix = [
        'components/ui/ChecklistProgress.tsx',
        'components/prototype/services/GibddCheckModal.tsx',
        'components/assistant/TrainerChat.tsx',
        'components/payments/PromoCodeInput.tsx',
        'components/ui/DocumentUploader.tsx',
        'components/ui/RiskIndicator.tsx',
        'components/ui/INNInput.tsx',
        'components/prototype/services/PatentPaymentModal.tsx',
        'app/(main)/profile/components/FormsTab.tsx',
        'lib/hooks/useAuth.ts',
        'lib/hooks/useHousing.ts',
        'lib/hooks/usePushNotifications.ts',
        'lib/stores/documentCheckStore.ts',
        'lib/stores/trainerStore.ts',
        'app/(main)/profile/components/DocumentTypeSelector.tsx',
        'components/prototype/wizard/steps/ScanningStep.tsx',
        'components/prototype/services/DocumentGenerator.tsx',
        'components/prototype/services/PassportValidityModal.tsx',
        'components/prototype/services/FAQModal.tsx',
        'components/paywall/PlanCard.tsx',
        'components/prototype/dashboard/AssistantScreen.tsx',
        'components/work/reviews/ReviewFormWizard.tsx',
        'components/paywall/PaywallSheet.tsx',
        'components/sos/LostDocumentsModal.tsx',
        'components/document-status/CheckResultModal.tsx',
        'components/work/EmployerComplaint.tsx',
        'components/work/EmployerCheck.tsx',
        'components/work/EmployerRating.tsx',
        'components/work/JobSearchHub.tsx',
        'components/work/ContractCheckResult.tsx',
        'components/work/ResumeBuilder.tsx',
        'components/work/ResumePreview.tsx',
        'components/work/EmploymentContractCheck.tsx',
        'components/housing/LandlordCheckResult.tsx',
        'components/housing/HousingSearchHub.tsx',
        'components/housing/ContractGenerator.tsx',
        'components/housing/ContractPreview.tsx',
        'components/housing/ContractCheckResult.tsx',
        'components/housing/HousingFilters.tsx',
        'components/housing/RegistrationGuide.tsx',
        'components/housing/ContractAICheck.tsx',
        'components/housing/LandlordRating.tsx',
        'components/housing/CreateReviewForm.tsx',
        'components/housing/ContractStep2.tsx',
        'components/housing/ContractStep3.tsx',
        'components/housing/LandlordCheckForm.tsx',
        'components/housing/LandlordReviews.tsx',
        'components/housing/ContractStep1.tsx',
        'components/housing/ContractStep4.tsx',
        'components/housing/HousingCard.tsx',
        'components/family/SchoolCard.tsx',
        'components/family/SchoolSearch.tsx',
        'components/family/FamilyReunionChecklist.tsx',
        'components/family/CostSummary.tsx',
        'components/family/DocumentCalculator.tsx',
        'components/family/DocumentItem.tsx',
        'components/family/SchoolDocuments.tsx',
        'components/checks/CheckResult.tsx',
        'components/payments/SbpPaymentModal.tsx',
        'components/assistant/AIChatPanel.tsx',
        'components/assistant/LawyerModal.tsx',
        'components/ui/EncryptedImage.tsx',
        'features/exam/components/ExamSession.tsx',
        'features/exam/components/ExamHome.tsx',
        'features/services/components/BanChecker.tsx',
        'components/settings/ReferralSection.tsx',
        'components/security/RecoveryCodeModal.tsx',
        'components/security/RecoveryForm.tsx',
        'components/prototype/services/WorkPermitCheckModal.tsx',
        'components/prototype/dashboard/DocumentsScreen.tsx',
        'components/prototype/dashboard/RoadmapScreen.tsx',
        'components/modals/DeleteAccountModal.tsx',
        'components/documents/DocumentScanner.tsx',
        'components/documents/ExportPdfModal.tsx',
        'components/ai/AiQuotaSection.tsx',
        'components/consent/ConsentCheckbox.tsx',
        'components/sos/SOSScreen.tsx',
        'components/prototype/dashboard/ServicesScreen.tsx',
        'features/services/components/StayCalculator.tsx',
        'components/prototype/dashboard/home/QRCodeModal.tsx',
        'components/prototype/dashboard/home/ProfileEditModal.tsx',
        'app/(main)/profile/components/QRCodeModal.tsx',
        'app/(main)/profile/components/ProfileTab.tsx',
        'components/prototype/dashboard/home/OtherServicesModal.tsx',
        'components/prototype/dashboard/home/HistoryModal.tsx',
        'components/prototype/dashboard/home/QuickActions.tsx',
        'components/prototype/dashboard/home/UrgentTasks.tsx',
        'components/prototype/dashboard/home/HomeHeader.tsx',
        'components/prototype/wizard/steps/ProcessingStep.tsx',
        'components/prototype/wizard/steps/VerificationStep.tsx',
        'components/prototype/wizard/steps/DocumentScanStep.tsx',
        'components/prototype/wizard/steps/AdditionalDocsStep.tsx',
        'components/prototype/wizard/steps/RequiredDocsStep.tsx',
        'components/prototype/wizard/steps/WizardIntro.tsx',
        'features/documents/components/DocumentCard.tsx',
        'components/modals/CreateBackupModal.tsx',
        'features/exam/components/ResultsScreen.tsx',
        'features/exam/components/CategoryCard.tsx',
        'features/exam/hooks/useExamSession.ts',
        'components/personal/LegalStatusCard.tsx',
        'components/settings/EmailSettingsSection.tsx',
        'components/ai/AiPackCard.tsx',
        'components/settings/NotificationSettings.tsx',
        'components/documents/MrzResultCard.tsx',
        'components/ui/SyncStatusBar.tsx',
        'features/exam/components/QuestionCard.tsx',
        'components/prototype/services/PatentCalculatorModal.tsx',
        'components/modals/DeleteBackupConfirm.tsx',
        'components/ui/ProgressRoadmap.tsx',
        'features/exam/components/ProgressBar.tsx',
        'features/services/components/DeportationModeWarning.tsx',
    ]

    fixed_count = 0
    error_count = 0

    print(f"🔧 Исправление {len(files_to_fix)} файлов с неправильным размещением useTranslation()...\n")

    for file_rel in files_to_fix:
        file_path = src_dir / file_rel
        if not file_path.exists():
            print(f"  ⚠️  Файл не найден: {file_rel}")
            error_count += 1
            continue

        try:
            if fix_file(file_path):
                print(f"  ✅ {file_rel}")
                fixed_count += 1
            else:
                print(f"  ⏭️  {file_rel} (без изменений)")
        except Exception as e:
            print(f"  ❌ {file_rel}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Исправлено: {fixed_count}")
    print(f"❌ Ошибок: {error_count}")
    print(f"⏭️  Пропущено: {len(files_to_fix) - fixed_count - error_count}")

if __name__ == '__main__':
    main()
