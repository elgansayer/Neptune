// Public, independently specified SH-2 fixture. No original-game bytes or semantics.
// @category Neptune
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.UnsignedIntegerDataType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.lang.Register;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Iterator;

public class provision_ghidra_smoke extends GhidraScript {
    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1) throw new Exception("One fresh observation path required");
        Address base = toAddr(0x06004000L);
        if (!currentProgram.getLanguageID().toString().equals("SuperH:BE:32:SH-2") ||
            !currentProgram.getMinAddress().equals(base) || currentProgram.getMemory().getSize() != 6)
            throw new Exception("Wrong SH-2 import identity");
        if (!disassemble(base)) throw new Exception("Disassembly failed");
        String[] expected = {"mov", "rts", "nop"};
        for (int i = 0; i < expected.length; ++i) {
            Instruction instruction = getInstructionAt(base.add(2 * i));
            if (instruction == null || instruction.getLength() != 2 ||
                !instruction.getMnemonicString().equalsIgnoreCase(expected[i]))
                throw new Exception("Wrong instruction at " + i);
        }
        Instruction first = getInstructionAt(base);
        Object[] immediate = first.getOpObjects(0), register = first.getOpObjects(1);
        if (immediate.length != 1 || !(immediate[0] instanceof Scalar) ||
            ((Scalar)immediate[0]).getUnsignedValue() != 42 || register.length != 1 ||
            !(register[0] instanceof Register) || !((Register)register[0]).getName().equalsIgnoreCase("r0"))
            throw new Exception("Wrong constant/register decoding");
        Function function = createFunction(base, "public_constant");
        if (function == null) throw new Exception("Missing public fixture function");
        function.setReturnType(UnsignedIntegerDataType.dataType, SourceType.USER_DEFINED);
        DecompInterface decompiler = new DecompInterface();
        boolean returned42 = false;
        try {
            if (!decompiler.openProgram(currentProgram)) throw new Exception("Decompiler unavailable");
            var result = decompiler.decompileFunction(function, 15, monitor);
            if (!result.decompileCompleted() || result.getHighFunction() == null)
                throw new Exception("Headless decompilation failed");
            Iterator<PcodeOpAST> operations = result.getHighFunction().getPcodeOps();
            while (operations.hasNext()) {
                PcodeOpAST operation = operations.next();
                if (operation.getOpcode() == PcodeOp.RETURN && operation.getNumInputs() == 2 &&
                    operation.getInput(1).isConstant() && operation.getInput(1).getOffset() == 42)
                    returned42 = true;
            }
        } finally { decompiler.dispose(); }
        if (!returned42) throw new Exception("Decompiler did not recover constant return42");
        String json = "{\"version\":\"" + Application.getApplicationVersion() +
            "\",\"language\":\"SuperH:BE:32:SH-2\",\"base\":\"06004000\"," +
            "\"instructions\":[\"mov\",\"rts\",\"nop\"],\"constant_return\":42}\n";
        Files.writeString(Path.of(getScriptArgs()[0]), json, java.nio.file.StandardOpenOption.CREATE_NEW);
    }
}
