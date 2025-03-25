import React, { useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableFooter,
  TablePagination,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { tableCellClasses } from '@mui/material/TableCell';

const ChatMessage = ({ message }) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Styled components for alternating row colors
  const StyledTableRow = styled(TableRow)(({ theme }) => ({
    '&:nth-of-type(odd)': {
      backgroundColor: theme.palette.action.hover,
    },
    '&:nth-of-type(even)': {
      backgroundColor: theme.palette.background.default,
    },
    // Ensure the last row doesn't have a border issue
    '&:last-child td, &:last-child th': {
      border: 0,
    },
  }));

  const StyledTableCell = styled(TableCell)(({ theme }) => ({
    [`&.${tableCellClasses.head}`]: {
      backgroundColor: theme.palette.common.black,
      color: theme.palette.common.white,
    },
    [`&.${tableCellClasses.body}`]: {
      fontSize: 14,
    },
  }));

  // Handle page change
  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  // Handle rows per page change
  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  // Paginate the table data
  const paginatedData =
    message.table?.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage) || [];

  return (
    <Box sx={{ mb: 2, display: 'flex', justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start' }}>
      <Box sx={{ maxWidth: '70%', p: 1, borderRadius: 2, bgcolor: message.type === 'user' ? 'primary.light' : 'grey.200' }}>
        <Typography variant="body1">{message.content}</Typography>
        {message.table && message.table.length > 0 && (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <StyledTableRow>
                {Object.keys(message.table[0]).map((header) => (
                  <StyledTableCell key={header}>{header}</StyledTableCell>
                ))}
              </StyledTableRow>
            </TableHead>
            <TableBody>
              {paginatedData.map((row, index) => (
                <StyledTableRow key={index}>
                  {Object.values(row).map((cell, cellIndex) => (
                    <StyledTableCell key={cellIndex}>{cell}</StyledTableCell>
                  ))}
                </StyledTableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TablePagination
                  rowsPerPageOptions={[10, 20, 50]}
                  count={message.table.length}
                  rowsPerPage={rowsPerPage}
                  page={page}
                  onPageChange={handleChangePage}
                  onRowsPerPageChange={handleChangeRowsPerPage}
                />
              </TableRow>
            </TableFooter>
          </Table>
        )}

      </Box>
    </Box>
  );
};

export default ChatMessage;
