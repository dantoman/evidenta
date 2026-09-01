import { BrowserRouter, Route, Routes } from 'react-router'

import { t } from '@/locales'
import { ApiError } from '@/shared/api/client'
import { LoginScreen } from './auth/LoginScreen'
import { useIdentity } from './auth/useIdentity'
import { AccountLedgerScreen } from './accounting/AccountLedgerScreen'
import { AccountScreen } from './accounting/AccountScreen'
import { CorrespondenceScreen } from './accounting/CorrespondenceScreen'
import { GeneralLedgerScreen } from './accounting/GeneralLedgerScreen'
import { ChartOfAccountsScreen } from './accounting/ChartOfAccountsScreen'
import { ChartSetupScreen } from './accounting/ChartSetupScreen'
import { JournalScreen } from './accounting/JournalScreen'
import { ManualEntryScreen } from './accounting/ManualEntryScreen'
import { OpeningBalancesScreen } from './accounting/OpeningBalancesScreen'
import { OperationTemplatesScreen } from './accounting/OperationTemplatesScreen'
import { RegisterScreen } from './accounting/RegisterScreen'
import { TrialBalanceScreen } from './accounting/TrialBalanceScreen'
import { CompaniesScreen } from './companies/CompaniesScreen'
import { DashboardScreen } from './dashboard/DashboardScreen'
import { CompanyScreen } from './companies/CompanyScreen'
import { PartnersScreen } from './partners/PartnersScreen'
import { WorkspaceScreen } from './workspace/WorkspaceScreen'
import { PurchasesScreen } from './purchases/PurchasesScreen'
import { SalesScreen } from './sales/SalesScreen'
import { SettlementsScreen } from './settlements/SettlementsScreen'
import { TreasuryScreen } from './treasury/TreasuryScreen'
import { ContractsScreen } from './payroll/ContractsScreen'
import { ExemptionsScreen } from './payroll/ExemptionsScreen'
import { IpcScreen } from './payroll/IpcScreen'
import { PayrollRunScreen } from './payroll/PayrollRunScreen'
import { PeopleScreen } from './payroll/PeopleScreen'
import { TimesheetScreen } from './payroll/TimesheetScreen'
import { AppLayout } from './layout/AppLayout'
import { Landing } from './layout/Landing'

/**
 * The whole routing decision, which is small on purpose.
 *
 * **No route ever carries a tenant identifier.** The tenant comes from the
 * subdomain (C8), so there is no `/:tenantId/` segment here and there will not
 * be one: a path that could name a tenant is a path someone can type.
 *
 * **A company identifier is a different thing entirely, and it belongs here.** A
 * tenant may hold several companies, each with its own ledger, so every
 * accounting screen has to say which -- and the server's own routes are shaped
 * the same way. Keeping the choice in component state, as the first version did,
 * meant one company's chart had no address: nothing could link to it and a
 * reload silently fell back to the first company in the list.
 *
 * Authentication gates the router rather than living inside it. A route guard
 * that ran per route would let a screen mount for a frame before redirecting,
 * and in an accounting product that frame can show somebody else's numbers.
 */
export function App() {
  const identity = useIdentity()

  if (identity.isPending) {
    return <p className="p-6 text-sm text-ink-muted">{t.app.loading}</p>
  }

  if (identity.isError) {
    // By code, not by one catch-all message. The first version printed
    // "Serverul nu răspunde" for every failure, and the owner hit it on a host
    // with no subdomain: the server had answered, correctly, 404 -- and the
    // screen blamed the network. A message that describes the wrong cause is
    // worse than no message, because it sends the reader to check the wrong
    // thing.
    const failure = identity.error instanceof ApiError ? identity.error : null
    return (
      <main className="p-6">
        <p role="alert" className="text-sm text-danger">
          {failure ? failure.display : t.errors.unknown}
        </p>
        {failure?.code === 'tenant.not_found' && (
          <p className="mt-2 text-sm text-ink-muted">{t.errors.hintSubdomain}</p>
        )}
      </main>
    )
  }

  if (!identity.data) {
    return <LoginScreen />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout tenantId={identity.data.tenant_id} />}>
          {/* One canonical address per screen. `/` redirects rather than
              rendering the list a second time under a second URL -- and it
              redirects into the account holder's books when there are any
              (ADR-075), because that is where a sign-in almost always goes. */}
          <Route index element={<Landing />} />
          <Route path="companii" element={<CompaniesScreen />} />
          <Route path="companii/:companyId" element={<CompanyScreen />} />
          {/* No company segment: a partner belongs to the workspace, and the
              same legal entity is the same entity for every company of it. */}
          <Route path="parteneri" element={<PartnersScreen />} />
          {/* Spatiul de lucru: titularul contului si drepturile din el. Fara
              segment de companie -- contractul e al spatiului, nu al uneia. */}
          <Route path="spatiu-de-lucru" element={<WorkspaceScreen />} />
          {/* The company's front page: what the month looks like, and what is
              not finished in it. */}
          <Route path="companii/:companyId/panou" element={<DashboardScreen />} />
          <Route
            path="companii/:companyId/plan-de-conturi"
            element={<ChartOfAccountsScreen />}
          />
          <Route
            path="companii/:companyId/plan-de-conturi/initializare"
            element={<ChartSetupScreen />}
          />
          <Route path="companii/:companyId/conturi/:accountId" element={<AccountScreen />} />
          {/* F1.8. The account's ledgers hang off the account, the chess-board
              off the company -- the same shapes as the server's routes. */}
          <Route
            path="companii/:companyId/conturi/:accountId/fisa"
            element={<AccountLedgerScreen />}
          />
          <Route
            path="companii/:companyId/conturi/:accountId/cartea-mare"
            element={<GeneralLedgerScreen />}
          />
          <Route path="companii/:companyId/rulaje" element={<CorrespondenceScreen />} />
          <Route path="companii/:companyId/jurnale" element={<JournalScreen />} />
          <Route path="companii/:companyId/note" element={<ManualEntryScreen />} />
          <Route path="companii/:companyId/balanta" element={<TrialBalanceScreen />} />
          <Route path="companii/:companyId/registru" element={<RegisterScreen />} />
          {/* Facturi emise: documentul și contarea lui, într-un singur pas. */}
          <Route path="companii/:companyId/facturi" element={<SalesScreen />} />
          <Route
            path="companii/:companyId/facturi-primite"
            element={<PurchasesScreen />}
          />
          <Route path="companii/:companyId/trezorerie" element={<TreasuryScreen />} />
          <Route
            path="companii/:companyId/solduri-deschise"
            element={<SettlementsScreen />}
          />
          <Route path="companii/:companyId/sabloane" element={<OperationTemplatesScreen />} />
          {/* With and without a batch: the batch id is in the path so a draft
              survives a reload -- the server has no way to list a company's
              batches yet, so an address is the only way back to one. */}
          <Route
            path="companii/:companyId/solduri-initiale"
            element={<OpeningBalancesScreen />}
          />
          <Route
            path="companii/:companyId/solduri-initiale/:batchId"
            element={<OpeningBalancesScreen />}
          />
          {/* Salarizarea stă SUB companie, spre deosebire de parteneri:
              angajatorul legal e compania — ea reține, ea depune, ea răspunde. */}
          <Route path="companii/:companyId/angajati" element={<PeopleScreen />} />
          <Route path="companii/:companyId/contracte" element={<ContractsScreen />} />
          <Route path="companii/:companyId/pontaj" element={<TimesheetScreen />} />
          <Route path="companii/:companyId/salarii" element={<PayrollRunScreen />} />
          {/* Darea de seamă lunară: un document, nu trei rapoarte (art. 5 alin. (1)). */}
          <Route path="companii/:companyId/darea-de-seama" element={<IpcScreen />} />
          {/* Scutirile atârnă de persoană: cererea e a ei, iar pct. 18 o datează. */}
          <Route
            path="companii/:companyId/angajati/:employeeId/scutiri"
            element={<ExemptionsScreen />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
