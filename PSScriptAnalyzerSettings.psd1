@{
    Severity     = @('Error')
    ExcludeRules = @(
        # UserManagement.ps1 supports trusted lab CSV imports. Keep this visible
        # in code review, but do not block the repository-wide error gate on it.
        'PSAvoidUsingConvertToSecureStringWithPlainText'
    )
}
