import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import RegistrationForm from './RegistrationForm'
import { deferred, response } from './test/fixtures'

async function fillRegistration(user, courses = 'CSC 510, CSC 540, ') {
  const fields = [
    ['Full name', 'Alex Morgan'],
    ['Email address', 'alex@example.test'],
    ['Password', 'test-password-123'],
    ['Confirm password', 'test-password-123'],
    ['Program', 'MS Computer Science'],
    ['Year of study', 'Second Year'],
  ]
  if (courses) fields.push(['Completed courses (optional)', courses])
  for (const [label, value] of fields)
    await user.type(screen.getByLabelText(label, { exact: true }), value)
  await user.click(screen.getByRole('checkbox'))
}

function mockApi(register, courses = []) {
  fetch.mockImplementation((url) =>
    url.startsWith('/api/courses?')
      ? Promise.resolve(response({ courses }))
      : register(),
  )
}
const registerCalls = () =>
  fetch.mock.calls.filter(([url]) => url === '/api/auth/register')

describe('registration', () => {
  it('submits account/profile data once, shows success and returns to sign in', async () => {
    const user = userEvent.setup()
    const pending = deferred()
    mockApi(() => pending.promise)
    const onRegistered = vi.fn()
    const onClose = vi.fn()
    render(
      <RegistrationForm
        apiUrl=""
        onRegistered={onRegistered}
        onClose={onClose}
      />,
    )
    await fillRegistration(user)
    await user.dblClick(screen.getByRole('button', { name: 'Create account' }))
    expect(
      screen.getByRole('button', { name: 'Creating account...' }),
    ).toBeDisabled()
    expect(registerCalls()).toHaveLength(1)
    expect(registerCalls()[0]).toEqual([
      '/api/auth/register',
      expect.objectContaining({ method: 'POST' }),
    ])
    expect(JSON.parse(registerCalls()[0][1].body)).toMatchObject({
      email: 'alex@example.test',
      completed_courses: ['CSC 510', 'CSC 540'],
      willing_to_advise: true,
    })
    pending.resolve(response({ student: { id: 1 } }, 201))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'account and student profile have been created',
    )
    expect(onRegistered).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Back to sign in' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows API feedback and permits retry without losing fields', async () => {
    const user = userEvent.setup()
    let attempts = 0
    mockApi(() =>
      Promise.resolve(
        ++attempts === 1
          ? response({ error: 'Email is already registered.' }, 409)
          : response({}, 201),
      ),
    )
    const onRegistered = vi.fn()
    render(
      <RegistrationForm
        apiUrl=""
        onRegistered={onRegistered}
        onClose={vi.fn()}
      />,
    )
    await fillRegistration(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Email is already registered.',
    )
    expect(onRegistered).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Email address')).toHaveValue(
      'alex@example.test',
    )
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'have been created',
    )
  })

  it('fills completed courses from catalog suggestions', async () => {
    const user = userEvent.setup()
    mockApi(
      () => Promise.resolve(response({ student: { id: 1 } }, 201)),
      [{ code: 'CSC 510', title: 'Software Engineering' }],
    )
    render(
      <RegistrationForm apiUrl="" onRegistered={vi.fn()} onClose={vi.fn()} />,
    )
    await fillRegistration(user, '')
    const courses = screen.getByRole('combobox', {
      name: 'Completed courses (optional)',
    })
    await user.type(courses, 'csc5')
    await user.click(
      await screen.findByRole('option', { name: /^CSC 510 Software/ }),
    )
    expect(courses).toHaveValue('CSC 510, ')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'have been created',
    )
    expect(JSON.parse(registerCalls()[0][1].body).completed_courses).toEqual([
      'CSC 510',
    ])
  })
})
