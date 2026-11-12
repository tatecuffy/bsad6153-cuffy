# Proposed Milestone 2 read-only access

## Requirement and status

The course repository's Week 2 instructions in `db/roles.sql` require a
read-only role for the website, chatbot, and reference-question checker.
`docs/README.md` also requires access-role documentation. The exact Canvas
rubric has not been independently reviewed.

The password-free proposal in `db/roles.sql` has **not been executed**. No live
role configuration, grants, private authentication setup, or permission tests
were performed during this preparation. The deployed data and schema are
unchanged. This access requirement remains pending live authorization.

## Proposed permissions

| Principal | Intended access |
|---|---|
| Provisioning/loading connection | Existing authorized schema and load work; never used by the website. |
| `app_reader` | LOGIN, schema USAGE, and SELECT on the three named data tables. |

The new role has no superuser, database creation, role creation, replication,
or RLS bypass privileges. No inherited role memberships, table writes, sequence
access, or default grants on future tables are included. The script creates
the role and grants in one transaction and fails if the role already exists.
It does not alter passwords or broaden application access for later milestones.

PostgreSQL privileges are additive. Effective access can also come from PUBLIC,
ownership, functions, or role memberships. Before applying the proposal, inspect
the live role catalog and PUBLIC grants; these cannot be established from the
local SQL file. Do not change shared PUBLIC permissions automatically. If
unexpected access or an existing role is found, stop for review. NOINHERIT
alone is not a substitute for reviewing memberships or PUBLIC privileges.
If row-level security applies, table SELECT alone may not expose rows; inspect
applicable policies without adding broad policies automatically.

## Implementation and verification after separate approval

1. Inspect the existing role and effective permissions without displaying
   credentials. Apply the reviewed SQL only if its prerequisites hold.
2. Configure authentication privately through the trusted provisioning workflow;
   store only the limited role's connection in ignored `APP_DATABASE_URL`.
   Do not commit authentication commands containing a real password.
3. Run `python scripts/check_db.py --app`, keeping connection details private.
4. As the limited role, confirm SELECT returns 20 countries, three indicators,
   and 960 observations, and that the five analytical queries succeed.
5. Check effective privileges: SELECT should be allowed; INSERT, UPDATE, DELETE,
   TRUNCATE, REFERENCES, and TRIGGER should be denied on the three data tables.
   Check that the role neither owns tables nor has unexpected memberships or
   schema CREATE privileges. Review any additional capabilities via PUBLIC.
6. Verify a write is denied using a controlled test with no matching rows,
   inside an explicitly rolled-back transaction. For example, an UPDATE of
   `countries.name` with `WHERE FALSE` should fail on permissions without
   changing any record. If it succeeds, stop and review effective privileges.

Record actual results only after these steps occur. Do not claim that this
proposal is already deployed or that the read-only connection is verified.
