from docx import Document
document = Document()
logo = open('logos', 'r')                  #the logo path that is to be attached
document.add_heading('Underground Heating Oil Tank Search Report', 0) #simple heading that will come bellow the logo in the header.
document.save('report for xyz.docx') 