import { render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { CommandBar } from '../CommandBar'
import { vi } from 'vitest'

describe('CommandBar', () => {
  const mockOnFiltersChange = vi.fn()
  const mockOnStageFilterChange = vi.fn()
  const mockOnProcessImages = vi.fn()
  const mockOnExport = vi.fn()
  const mockOnToggleWorkflow = vi.fn()
  const mockOnSaveApproved = vi.fn()

  const defaultFilters = {
    medoidsOnly: false,
    unapprovedOnly: false,
    hideAfterSave: false,
    centerCrop: false,
  }

  const defaultSummaryCounts = {
    new: 5,
    needs_tags: 3,
    has_draft: 2,
    saved: 10,
    blocked: 1,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all stage filter options', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('New')).toBeInTheDocument()
    expect(screen.getByText('Needs tags')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByText('Blocked')).toBeInTheDocument()
  })

  it('displays summary chips when "all" stage is selected', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    expect(screen.getByText('Summary:')).toBeInTheDocument()

    // Check summary chips using container approach
    const summaryContainer = screen.getByText('Summary:').parentElement?.parentElement
    expect(summaryContainer).toHaveTextContent('New: 5')
    expect(summaryContainer).toHaveTextContent('Needs: 3')
    expect(summaryContainer).toHaveTextContent('Draft: 2')
    expect(summaryContainer).toHaveTextContent('Saved: 10')
    expect(summaryContainer).toHaveTextContent('Blocked: 1')
  })

  it('hides summary chips when a specific stage is selected', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="saved"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    expect(screen.queryByText('Summary:')).not.toBeInTheDocument()
    expect(screen.queryByText('New: 5')).not.toBeInTheDocument()
  })

  it('calls onStageFilterChange when stage filter is changed', async () => {
    const user = userEvent.setup()

    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    const newStageButton = screen.getByText('New')
    await user.click(newStageButton)

    expect(mockOnStageFilterChange).toHaveBeenCalledWith('new')
  })

  it('calls onFiltersChange when filter toggles are clicked', async () => {
    const user = userEvent.setup()

    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    const medoidsOnlyToggle = screen.getByText('Medoids')
    await user.click(medoidsOnlyToggle)

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      medoidsOnly: true,
    })
  })

  it('displays zero counts when no items are present', () => {
    const emptyCounts = {
      new: 0,
      needs_tags: 0,
      has_draft: 0,
      saved: 0,
      blocked: 0,
    }

    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={emptyCounts}
      />
    )

    // Check summary chips using container approach
    const emptySummaryContainer = screen.getByText('Summary:').parentElement?.parentElement
    expect(emptySummaryContainer).toHaveTextContent('New: 0')
    expect(emptySummaryContainer).toHaveTextContent('Needs: 0')
    expect(emptySummaryContainer).toHaveTextContent('Draft: 0')
    expect(emptySummaryContainer).toHaveTextContent('Saved: 0')
    expect(emptySummaryContainer).toHaveTextContent('Blocked: 0')
  })

  it('disables all controls when processing', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        onProcessImages={mockOnProcessImages}
        onExport={mockOnExport}
        onToggleWorkflow={mockOnToggleWorkflow}
        onSaveApproved={mockOnSaveApproved}
        processing={true}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    expect(screen.getByText('Processing…')).toBeDisabled()
    expect(screen.getByText('Medoids')).toBeDisabled()
    expect(screen.getByText('Unapproved')).toBeDisabled()
    expect(screen.getByText('Hide saved')).toBeDisabled()
    expect(screen.getByText('Center')).toBeDisabled()
    expect(screen.getByText('Save approved')).toBeDisabled()
    expect(screen.getByText('Workflow')).toBeDisabled()
    expect(screen.getByText('Export ▾')).toBeDisabled()
  })

  it('shows destructive variant when processing is needed', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        onProcessImages={mockOnProcessImages}
        needsProcessing={true}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    const processButton = screen.getByText('Process images')
    expect(processButton).toHaveClass('bg-destructive')
  })

  it('applies visual states to filter toggles', () => {
    render(
      <CommandBar
        filters={{ ...defaultFilters, medoidsOnly: true, hideAfterSave: true }}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    const medoidsToggle = screen.getByText('Medoids')
    const hideSavedToggle = screen.getByText('Hide saved')

    expect(medoidsToggle).toHaveClass('data-[state=on]:bg-blue-100')
    expect(hideSavedToggle).toHaveClass('data-[state=on]:bg-green-100')
  })

  it('displays tabular numbers in summary chips', () => {
    render(
      <CommandBar
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
        stageFilter="all"
        onStageFilterChange={mockOnStageFilterChange}
        summaryCounts={defaultSummaryCounts}
      />
    )

    const summaryContainer = screen.getByText('Summary:').parentElement?.parentElement
    expect(summaryContainer).toHaveTextContent('New: 5')
    expect(summaryContainer).toHaveTextContent('Needs: 3')
    expect(summaryContainer).toHaveTextContent('Draft: 2')
    expect(summaryContainer).toHaveTextContent('Saved: 10')
    expect(summaryContainer).toHaveTextContent('Blocked: 1')

    // Check for tabular-nums class
    const numberElements = summaryContainer?.querySelectorAll('.tabular-nums')
    expect(numberElements).toHaveLength(5)
  })
})
